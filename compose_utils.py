from pathlib import Path
from textwrap import dedent
import docker  # type: ignore
from platformdirs import user_cache_dir

COMPOSE_FILES_DIR = Path(user_cache_dir("inspect_mlebench_eval")) / "compose_files"


def get_compose_file(competition_id: str, data_dir: Path | str, docker_image_name: str, force_rebuild: bool = False) -> str:
    image_compose_file = COMPOSE_FILES_DIR / f"{competition_id}.yaml"
    image_compose_file.parent.mkdir(parents=True, exist_ok=True)

    with image_compose_file.open(mode="w+") as f:
        f.write(dedent(f"""\
            services:
              default:
                image: {docker_image_name}
                platform: linux/amd64
                network_mode: none
                entrypoint: ["/bin/sh", "-c", "rm -f /home/instructions_obfuscated.txt && exec /entrypoint.sh"]
                volumes:
                  - {Path(data_dir) / competition_id / "prepared" / "public"}:/home/data:ro
                  - {Path(data_dir) / competition_id / "prepared" / "private"}:/private/data/{competition_id}/prepared/private:ro
                environment:
                  - COMPETITION_ID={competition_id}
                x-local: true
                deploy:
                  resources:
                    limits:
                      cpus: '1'
        """))

        try:
            docker.from_env().images.get(docker_image_name)
            image_exists = True
        except docker.errors.ImageNotFound:
            image_exists = False

        if force_rebuild or not image_exists:
            f.write(f"    build: {Path(__file__).parent}")

    return str(image_compose_file)

def get_compose_file_aide(competition_id: str, data_dir: Path | str, docker_image_name: str, force_rebuild: bool = False) -> str:
    image_compose_file = COMPOSE_FILES_DIR / f"{competition_id}.yaml"
    image_compose_file.parent.mkdir(parents=True, exist_ok=True)

    with image_compose_file.open(mode="w+") as f:
        f.write(dedent(f"""\
            services:
              default:
                image: {docker_image_name}
                platform: linux/amd64
                volumes:
                  - {Path(data_dir) / competition_id / "prepared/public"}:/home/data:ro
                  - {Path(data_dir) / competition_id / "prepared/private"}:/private/data/{competition_id}/prepared/private:ro
                environment:
                  - COMPETITION_ID={competition_id}
                x-local: true
                deploy:
                  resources:
                    limits:
                      cpus: '1'
        """))


        try:
            docker.from_env().images.get(docker_image_name)
            image_exists = True
        except docker.errors.ImageNotFound:
            image_exists = False

        if force_rebuild or not image_exists:
            f.write(f"    build: {Path(__file__).parent / 'aide'}")

    return str(image_compose_file)
