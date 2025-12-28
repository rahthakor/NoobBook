"""
Wireframe Service - Generates UI/UX wireframes using Excalidraw elements.

Single AI call service that uses Claude to generate Excalidraw-compatible
element definitions for wireframe creation.
"""

from typing import Dict, Any
from datetime import datetime

from app.services.integrations.claude import claude_service
from app.services.source_services import source_index_service
from app.services.studio_services import studio_index_service
from app.config import prompt_loader, tool_loader
from app.utils import claude_parsing_utils
from app.utils.source_content_utils import get_source_content
from app.utils.excalidraw_utils import convert_to_excalidraw_elements


class WireframeService:
    """Service for generating UI/UX wireframes from source content."""

    def __init__(self):
        self._prompt_config = None
        self._tool = None

    def _load_config(self) -> Dict[str, Any]:
        if self._prompt_config is None:
            self._prompt_config = prompt_loader.get_prompt_config("wireframe")
        return self._prompt_config

    def _load_tool(self) -> Dict[str, Any]:
        if self._tool is None:
            self._tool = tool_loader.load_tool("studio_tools", "wireframe_tool")
        return self._tool

    def generate_wireframe(
        self,
        project_id: str,
        source_id: str,
        job_id: str,
        direction: str = "Create a wireframe for the main page layout."
    ) -> Dict[str, Any]:
        """
        Generate a wireframe for a source.

        Args:
            project_id: The project UUID
            source_id: The source UUID
            job_id: The job ID for status tracking
            direction: User's direction for what to wireframe

        Returns:
            Dict with success status, elements, and metadata
        """
        started_at = datetime.now()

        # Update job to processing
        studio_index_service.update_wireframe_job(
            project_id, job_id,
            status="processing",
            progress="Reading source content...",
            started_at=datetime.now().isoformat()
        )

        print(f"[Wireframe] Starting job {job_id}")

        try:
            # Get source metadata
            source = source_index_service.get_source_from_index(project_id, source_id)
            if not source:
                raise ValueError(f"Source {source_id} not found")

            source_name = source.get("name", "Unknown")

            # Get source content using shared utility
            studio_index_service.update_wireframe_job(
                project_id, job_id,
                progress="Analyzing content..."
            )

            content = get_source_content(project_id, source_id, max_chars=12000)
            print(f"[Wireframe] Content length: {len(content) if content else 0}")
            if not content or content.startswith("Error"):
                raise ValueError("No content found for source")

            # Load config and tool
            config = self._load_config()
            tool = self._load_tool()

            # Build the user message
            user_message = config["user_message_template"].format(
                direction=direction,
                content=content[:12000]
            )

            # Call Claude with the wireframe tool
            studio_index_service.update_wireframe_job(
                project_id, job_id,
                progress="Generating wireframe..."
            )

            response = claude_service.send_message(
                messages=[{"role": "user", "content": user_message}],
                system_prompt=config["system_prompt"],
                model=config["model"],
                max_tokens=config["max_tokens"],
                temperature=config["temperature"],
                tools=[tool],
                tool_choice={"type": "tool", "name": "generate_wireframe"},
                project_id=project_id
            )

            # Extract tool use result
            print(f"[Wireframe] Response stop_reason: {response.get('stop_reason')}")
            print(f"[Wireframe] Content blocks: {len(response.get('content_blocks', []))}")

            tool_inputs_list = claude_parsing_utils.extract_tool_inputs(
                response, "generate_wireframe"
            )

            print(f"[Wireframe] Tool inputs list: {tool_inputs_list}")

            if not tool_inputs_list or "elements" not in tool_inputs_list[0]:
                raise ValueError("Failed to generate wireframe - no elements returned")

            tool_inputs = tool_inputs_list[0]
            raw_elements = tool_inputs["elements"]
            title = tool_inputs.get("title", "Wireframe")
            description = tool_inputs.get("description", "")
            canvas_width = tool_inputs.get("canvas_width", 1200)
            canvas_height = tool_inputs.get("canvas_height", 800)

            # Convert to Excalidraw format
            studio_index_service.update_wireframe_job(
                project_id, job_id,
                progress="Formatting wireframe..."
            )

            excalidraw_elements = convert_to_excalidraw_elements(raw_elements)

            # Calculate generation time
            generation_time = (datetime.now() - started_at).total_seconds()

            # Update job with results
            studio_index_service.update_wireframe_job(
                project_id, job_id,
                status="ready",
                progress="Complete",
                title=title,
                description=description,
                elements=excalidraw_elements,
                canvas_width=canvas_width,
                canvas_height=canvas_height,
                element_count=len(excalidraw_elements),
                generation_time_seconds=round(generation_time, 1),
                completed_at=datetime.now().isoformat()
            )

            print(f"[Wireframe] Generated {len(excalidraw_elements)} elements in {generation_time:.1f}s")

            return {
                "success": True,
                "title": title,
                "description": description,
                "elements": excalidraw_elements,
                "element_count": len(excalidraw_elements),
                "source_name": source_name,
                "generation_time": generation_time
            }

        except Exception as e:
            print(f"[Wireframe] Error: {e}")
            studio_index_service.update_wireframe_job(
                project_id, job_id,
                status="error",
                error=str(e),
                completed_at=datetime.now().isoformat()
            )
            return {
                "success": False,
                "error": str(e)
            }


# Singleton instance
wireframe_service = WireframeService()
