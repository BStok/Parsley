# def deploy():
#     client = paramiko.SSHClient()
#     client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
#     client.connect(hostname=HOST, username=USER, key_filename=KEY_PATH)

#     run_remote(client, f"docker pull {IMAGE}")
#     run_remote(client, f"docker stop {container_name} || true")
#     run_remote(client, f"docker rm {container_name} || true")
#     run_remote(client, f"docker run -d --name {container_name} --restart unless-stopped -p {PORT}:{PORT} {IMAGE}")

#     client.close()