import os

import boto3
from botocore.config import Config

URL_VALIDADE_SEGUNDOS = 600


def _endpoint():
    return os.environ["S3_ENDPOINT"].rstrip("/")


def _bucket():
    return os.environ["S3_BUCKET"]


def _cliente():
    return boto3.client(
        "s3",
        endpoint_url=_endpoint(),
        aws_access_key_id=os.environ["S3_ACCESS_KEY"],
        aws_secret_access_key=os.environ["S3_SECRET_KEY"],
        region_name=os.environ.get("S3_REGION", "garage"),
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def enviar(chave, dados, content_type):
    _cliente().put_object(Bucket=_bucket(), Key=chave, Body=dados, ContentType=content_type)


def apagar(chave):
    _cliente().delete_object(Bucket=_bucket(), Key=chave)


def url_temporaria(chave):
    url = _cliente().generate_presigned_url(
        "get_object",
        Params={"Bucket": _bucket(), "Key": chave},
        ExpiresIn=URL_VALIDADE_SEGUNDOS,
    )
    # O Garage não tem porta publicada, então o navegador pede a URL assinada
    # pro catálogo (rota /fotos), que só repassa pro Garage do jeito que veio.
    return "/fotos" + url[len(_endpoint()):]


def url_interna(caminho, query_string):
    return f"{_endpoint()}/{caminho}?{query_string}"
