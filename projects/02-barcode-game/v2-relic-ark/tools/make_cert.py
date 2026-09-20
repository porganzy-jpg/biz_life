"""휴대폰 카메라용 자체 서명 HTTPS 인증서 생성 → certs/cert.pem, certs/key.pem
브라우저는 HTTPS(또는 localhost)에서만 카메라를 허용한다. 휴대폰에서 처음 접속 시 '안전하지 않음' 경고를 한 번 통과해야 한다."""
import datetime
import ipaddress
import socket
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

OUT = Path(__file__).resolve().parent.parent / "certs"
OUT.mkdir(exist_ok=True)


def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    finally:
        s.close()


key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
ip = lan_ip()
name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "relic-ark.local")])
san = x509.SubjectAlternativeName([
    x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1")), x509.IPAddress(ipaddress.ip_address(ip)),
])
now = datetime.datetime.now(datetime.timezone.utc)
cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
        .serial_number(x509.random_serial_number()).not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=365)).add_extension(san, critical=False)
        .sign(key, hashes.SHA256()))
(OUT / "key.pem").write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
                                                 serialization.NoEncryption()))
(OUT / "cert.pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
print(f"certs/ 생성 완료. SAN: localhost, 127.0.0.1, {ip}")
