"""Self-signed code-signing certificate for the macOS bundle (no Apple developer account).

    python -m firestone_bot.tools.mac_codesign create        # once, on the maintainer's Mac
    python -m firestone_bot.tools.mac_codesign export out.p12 PASSWORD   # for the CI secret
    python -m firestone_bot.tools.mac_codesign import-keychain cert.p12 PASSWORD   # CI
    python -m firestone_bot.tools.mac_codesign sign dist/FirestoneBot.app
    python -m firestone_bot.tools.mac_codesign trust        # redo the trust prompt

Why: macOS ties the Screen Recording / Accessibility grants to the app's code-signing
identity. An ad-hoc signature changes at every build, so users are asked again after each
update; a self-signed certificate keeps the identity stable (Gatekeeper still warns once,
right-click > Open, since the app is not notarised).

The certificate and its private key live in a dedicated keychain file
(~/Library/Keychains/firestone-bot.keychain-db); the certificate alone is also kept as
~/Library/Application Support/FirestoneBot/codesign-cert.pem. The identity's common name is
"Firestone Bot" (FIRESTONE_CODESIGN_IDENTITY for the spec).

Trust: codesign only uses a certificate the system trusts for code signing. On the
maintainer's Mac `security add-trusted-cert` opens a macOS password prompt once (user trust
settings cannot be written silently); on a CI runner (CI=true) the certificate goes into the
System keychain with passwordless sudo instead. The PKCS12 export uses -legacy: macOS's
`security import` rejects the OpenSSL 3 default (AES/PBKDF2) container.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

IDENTITY = "Firestone Bot"
KEYCHAIN = os.path.expanduser("~/Library/Keychains/firestone-bot.keychain-db")
KEYCHAIN_PASSWORD = "firestone-bot"  # protects nothing sensitive: a self-signed signing key
CERT_PEM = os.path.expanduser("~/Library/Application Support/FirestoneBot/codesign-cert.pem")


def _run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    print("+", " ".join(cmd))
    return subprocess.run(cmd, check=True, text=True, **kw)


def ensure_keychain() -> None:
    if not os.path.exists(KEYCHAIN):
        _run(["security", "create-keychain", "-p", KEYCHAIN_PASSWORD, KEYCHAIN])
        _run(["security", "set-keychain-settings", KEYCHAIN])  # no auto-lock
    _run(["security", "unlock-keychain", "-p", KEYCHAIN_PASSWORD, KEYCHAIN])
    current = (
        subprocess.run(
            ["security", "list-keychains", "-d", "user"],
            capture_output=True,
            text=True,
            check=False,
        )
        .stdout.replace('"', "")
        .split()
    )
    if KEYCHAIN not in current:
        _run(["security", "list-keychains", "-d", "user", "-s", *current, KEYCHAIN])


def create() -> None:
    """Create the certificate with openssl (10 years, codeSigning EKU) and import it."""
    ensure_keychain()
    with tempfile.TemporaryDirectory() as tmp:
        cfg = os.path.join(tmp, "openssl.cnf")
        with open(cfg, "w") as f:
            f.write(
                "[req]\ndistinguished_name=dn\nx509_extensions=ext\nprompt=no\n"
                f"[dn]\nCN={IDENTITY}\nO=Firestone Bot\n"
                "[ext]\nkeyUsage=critical,digitalSignature\nextendedKeyUsage=critical,codeSigning\n"
                "basicConstraints=critical,CA:false\nsubjectKeyIdentifier=hash\n"
            )
        key, crt, p12 = (os.path.join(tmp, n) for n in ("key.pem", "cert.pem", "cert.p12"))
        _run(
            [
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-nodes",
                "-days",
                "3650",
                "-keyout",
                key,
                "-out",
                crt,
                "-config",
                cfg,
            ]
        )
        _run(
            [
                "openssl",
                "pkcs12",
                "-export",
                "-legacy",
                "-inkey",
                key,
                "-in",
                crt,
                "-out",
                p12,
                "-passout",
                f"pass:{KEYCHAIN_PASSWORD}",
                "-name",
                IDENTITY,
            ]
        )
        os.makedirs(os.path.dirname(CERT_PEM), exist_ok=True)
        shutil.copy(crt, CERT_PEM)
        import_keychain(p12, KEYCHAIN_PASSWORD)
    print(f"created: identity '{IDENTITY}' in {KEYCHAIN}, certificate in {CERT_PEM}")


def import_keychain(p12: str, password: str) -> None:
    ensure_keychain()
    _run(
        [
            "security",
            "import",
            p12,
            "-k",
            KEYCHAIN,
            "-P",
            password,
            "-T",
            "/usr/bin/codesign",
            "-T",
            "/usr/bin/security",
        ]
    )
    # let codesign use the key without a GUI prompt
    _run(
        [
            "security",
            "set-key-partition-list",
            "-S",
            "apple-tool:,apple:,codesign:",
            "-s",
            "-k",
            KEYCHAIN_PASSWORD,
            KEYCHAIN,
        ],
        capture_output=True,
    )
    # a self-signed cert must be trusted for code signing, or codesign rejects it
    with tempfile.TemporaryDirectory() as tmp:
        crt = os.path.join(tmp, "cert.pem")
        _run(
            [
                "openssl",
                "pkcs12",
                "-in",
                p12,
                "-clcerts",
                "-nokeys",
                "-out",
                crt,
                "-passin",
                f"pass:{password}",
            ]
        )
        trust(crt)
    _run(["security", "find-identity", "-v", "-p", "codesigning", KEYCHAIN])


def trust(crt: str) -> None:
    """Trust the certificate for code signing: System keychain through sudo on CI, user
    trust settings (one macOS password prompt) on a desktop."""
    if os.environ.get("CI"):
        _run(
            [
                "sudo",
                "security",
                "add-trusted-cert",
                "-d",
                "-r",
                "trustRoot",
                "-p",
                "codeSign",
                "-k",
                "/Library/Keychains/System.keychain",
                crt,
            ]
        )
        return
    print("macOS asks for your password to trust the certificate for code signing (once).")
    r = subprocess.run(
        ["security", "add-trusted-cert", "-p", "codeSign", "-k", KEYCHAIN, crt],
        check=False,
        text=True,
        capture_output=True,
    )
    if r.returncode:
        print(
            "add-trusted-cert:",
            r.stderr.strip(),
            "- run `python -m firestone_bot.tools.mac_codesign trust` later",
        )


def export(out: str, password: str) -> None:
    ensure_keychain()
    _run(
        [
            "security",
            "export",
            "-k",
            KEYCHAIN,
            "-t",
            "identities",
            "-f",
            "pkcs12",
            "-P",
            password,
            "-o",
            out,
        ]
    )
    print(
        f"exported to {out}; CI secret: base64 < {out} | pbcopy -> MACOS_CERT_P12, password -> MACOS_CERT_PASSWORD"
    )


def sign(app: str) -> None:
    ensure_keychain()
    _run(
        [
            "codesign",
            "--force",
            "--deep",
            "--sign",
            IDENTITY,
            "--keychain",
            KEYCHAIN,
            "--timestamp=none",
            app,
        ]
    )
    _run(["codesign", "--verify", "--deep", "--strict", "--verbose=1", app])


def main(argv: list[str]) -> int:
    if sys.platform != "darwin":
        print("macOS only")
        return 1
    cmd = argv[:1]
    if cmd == ["create"]:
        create()
    elif cmd == ["export"] and len(argv) == 3:
        export(argv[1], argv[2])
    elif cmd == ["import-keychain"] and len(argv) == 3:
        import_keychain(argv[1], argv[2])
    elif cmd == ["sign"] and len(argv) == 2:
        sign(argv[1])
    elif cmd == ["trust"]:
        ensure_keychain()
        trust(CERT_PEM)
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
