# test_traefik.py

from traefik import build_traefik_labels


def test_build_traefik_labels():
    labels = build_traefik_labels(
        project_id="abc-123",
        subdomain="myproject",
        port=8000,
        base_domain="parsley.dev",
    )

    assert labels == [
        "--label traefik.enable=true",
        "--label traefik.http.routers.abc-123.rule=Host(`myproject.parsley.dev`)",
        "--label traefik.http.routers.abc-123.entrypoints=websecure",
        "--label traefik.http.routers.abc-123.tls.certresolver=letsencrypt",
        "--label traefik.http.services.abc-123.loadbalancer.server.port=8000",
    ]