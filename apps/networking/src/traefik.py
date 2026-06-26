# traefik.py

def build_traefik_labels(
    project_id: str,
    subdomain: str,
    port: int,
    base_domain: str,
) -> list[str]:
    return [
        "--label traefik.enable=true",
        f"--label \"traefik.http.routers.{project_id}.rule=Host(\\`{subdomain}.{base_domain}\\`)\"",
        f"--label traefik.http.routers.{project_id}.entrypoints=websecure",
        f"--label traefik.http.routers.{project_id}.tls.certresolver=letsencrypt",
        f"--label traefik.http.services.{project_id}.loadbalancer.server.port={port}",
    ]

def build_docker_run_command(
    image_tag: str,
    container_name: str,
    labels: list[str],
) -> str:
    label_str = " ".join(labels)
    return f"docker run -d --name {container_name} --network traefik-net --restart unless-stopped {label_str} {image_tag}"