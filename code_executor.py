# In code_executor.py

import os
import docker
import logging

logger = logging.getLogger(__name__)

def run_code_in_sandbox(code: str) -> dict:
    """
    Runs code in a container using a raw string for the absolute path
    to prevent unicode escape errors on Windows.
    """
    client = docker.from_env()
    container_name = "data-analyst-agent-sandbox"
    python_image = "data-analyst-image"
    container = None

    # --- THIS IS THE KEY CHANGE ---
    # Add an 'r' before the string to make it a raw string.
    workspace_path = r"C:\Users\23f20\OneDrive\Documents\data analyst agent\workspace"
    # --- END CHANGE ---

    try:
        # The rest of the function is unchanged
        client.images.get(python_image)
        try:
            existing_container = client.containers.get(container_name)
            existing_container.remove(force=True)
        except docker.errors.NotFound:
            pass

        logger.info("Creating and running the container...")
        command = ["python", "-c", code]
        
        container = client.containers.run(
            image=python_image,
            command=command,
            name=container_name,
            detach=True,
            remove=False,
            volumes={workspace_path: {'bind': '/app/workspace', 'mode': 'rw'}}
        )
        result = container.wait()
        stdout = container.logs(stdout=True, stderr=False).decode('utf-8')
        stderr = container.logs(stdout=False, stderr=True).decode('utf-8')
        logger.info(f"Execution finished. stdout: {stdout.strip()}, stderr: {stderr.strip()}")
        return {"stdout": stdout, "stderr": stderr, "exit_code": result.get('StatusCode', 0)}

    except Exception as e:
        logger.error(f"An unexpected error occurred in code_executor: {e}")
        return {"stdout": "", "stderr": str(e), "exit_code": -1}
    
    finally:
        if container:
            try:
                container.remove(force=True)
            except Exception as e:
                logger.error(f"Error during container cleanup: {e}")