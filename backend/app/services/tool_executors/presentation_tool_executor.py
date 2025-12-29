"""
Presentation Tool Executor - Handles tool execution for presentation agent.

Tool handlers extracted from presentation_agent_service.py for separation of concerns.
Agent handles orchestration, executor handles tool-specific logic.

Tools:
- plan_presentation: Plan slides, content, design system
- create_base_styles: Create brand CSS file
- create_slide: Create individual slide HTML files
- finalize_presentation: Termination tool - signals completion
"""

import os
from typing import Dict, Any, Tuple, List
from datetime import datetime
from pathlib import Path

from app.utils.path_utils import get_studio_dir
from app.services.studio_services import studio_index_service


class PresentationToolExecutor:
    """Executes presentation agent tools."""

    TERMINATION_TOOL = "finalize_presentation"

    def execute_tool(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], bool]:
        """
        Execute a tool and return result.

        Args:
            tool_name: Name of the tool to execute
            tool_input: Input parameters from Claude
            context: Execution context including:
                - project_id, job_id, source_id
                - created_files: List of created files (mutable)
                - slides_info: List of slide metadata (mutable)
                - iterations, input_tokens, output_tokens

        Returns:
            Tuple of (result_dict, is_termination)
            result_dict includes updated created_files and slides_info
        """
        project_id = context["project_id"]
        job_id = context["job_id"]
        created_files = context.get("created_files", [])
        slides_info = context.get("slides_info", [])

        if tool_name == "plan_presentation":
            result_msg = self._handle_plan(project_id, job_id, tool_input)
            return {
                "success": True,
                "message": result_msg,
                "created_files": created_files,
                "slides_info": slides_info
            }, False

        elif tool_name == "create_base_styles":
            result_msg, updated_files = self._handle_create_base_styles(
                project_id, job_id, tool_input, created_files
            )
            return {
                "success": True,
                "message": result_msg,
                "created_files": updated_files,
                "slides_info": slides_info
            }, False

        elif tool_name == "create_slide":
            result_msg, updated_files, updated_slides = self._handle_create_slide(
                project_id, job_id, tool_input, created_files, slides_info
            )
            return {
                "success": True,
                "message": result_msg,
                "created_files": updated_files,
                "slides_info": updated_slides
            }, False

        elif tool_name == "finalize_presentation":
            result = self._handle_finalize(
                project_id=project_id,
                job_id=job_id,
                source_id=context.get("source_id", ""),
                tool_input=tool_input,
                created_files=created_files,
                slides_info=slides_info,
                iterations=context.get("iterations", 0),
                input_tokens=context.get("input_tokens", 0),
                output_tokens=context.get("output_tokens", 0)
            )
            return result, True  # Termination

        else:
            return {
                "success": False,
                "message": f"Unknown tool: {tool_name}",
                "created_files": created_files,
                "slides_info": slides_info
            }, False

    def _handle_plan(
        self,
        project_id: str,
        job_id: str,
        tool_input: Dict[str, Any]
    ) -> str:
        """Handle plan_presentation tool call."""
        title = tool_input.get("presentation_title", "Untitled Presentation")
        slides = tool_input.get("slides", [])
        presentation_type = tool_input.get("presentation_type", "business")

        print(f"      Planning: {title} ({len(slides)} slides)")

        studio_index_service.update_presentation_job(
            project_id, job_id,
            presentation_title=title,
            presentation_type=presentation_type,
            target_audience=tool_input.get("target_audience"),
            planned_slides=slides,
            design_system=tool_input.get("design_system"),
            style_notes=tool_input.get("style_notes"),
            status_message=f"Planned {len(slides)}-slide presentation, creating base styles..."
        )

        return (
            f"Presentation plan saved successfully. Title: '{title}', "
            f"Type: {presentation_type}, Slides: {len(slides)}. "
            f"Now create base-styles.css with the design system colors."
        )

    def _handle_create_base_styles(
        self,
        project_id: str,
        job_id: str,
        tool_input: Dict[str, Any],
        created_files: List[str]
    ) -> Tuple[str, List[str]]:
        """Handle create_base_styles tool call."""
        content = tool_input.get("content", "")

        print(f"      Creating: base-styles.css ({len(content)} chars)")

        try:
            slides_dir = Path(get_studio_dir(project_id)) / "presentations" / job_id / "slides"
            slides_dir.mkdir(parents=True, exist_ok=True)

            file_path = slides_dir / "base-styles.css"

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)

            # Update created files list
            updated_files = created_files.copy()
            if "base-styles.css" not in updated_files:
                updated_files.append("base-styles.css")

            studio_index_service.update_presentation_job(
                project_id, job_id,
                files=updated_files,
                status_message="Base styles created, generating slides..."
            )

            print(f"      Saved: base-styles.css")

            return (
                f"base-styles.css created successfully ({len(content)} characters). "
                f"Now create slides starting with slide_01.html."
            ), updated_files

        except Exception as e:
            return f"Error creating base-styles.css: {str(e)}", created_files

    def _handle_create_slide(
        self,
        project_id: str,
        job_id: str,
        tool_input: Dict[str, Any],
        created_files: List[str],
        slides_info: List[Dict[str, Any]]
    ) -> Tuple[str, List[str], List[Dict[str, Any]]]:
        """Handle create_slide tool call."""
        slide_number = tool_input.get("slide_number", 1)
        slide_type = tool_input.get("slide_type", "bullet_points")
        content = tool_input.get("content", "")

        filename = f"slide_{slide_number:02d}.html"

        print(f"      Creating: {filename} ({slide_type}, {len(content)} chars)")

        try:
            slides_dir = Path(get_studio_dir(project_id)) / "presentations" / job_id / "slides"
            slides_dir.mkdir(parents=True, exist_ok=True)

            file_path = slides_dir / filename

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)

            # Update created files list
            updated_files = created_files.copy()
            if filename not in updated_files:
                updated_files.append(filename)

            # Update slides info list
            updated_slides = slides_info.copy()
            updated_slides.append({
                "filename": filename,
                "slide_number": slide_number,
                "slide_type": slide_type
            })

            # Update job
            slide_count = len([f for f in updated_files if f.startswith("slide_")])
            studio_index_service.update_presentation_job(
                project_id, job_id,
                files=updated_files,
                slides_created=slide_count,
                status_message=f"Created {filename} ({slide_count} slides so far)"
            )

            print(f"      Saved: {filename}")

            return (
                f"Slide {slide_number} ({filename}) created successfully. "
                f"Type: {slide_type}, Size: {len(content)} characters."
            ), updated_files, updated_slides

        except Exception as e:
            return f"Error creating slide {slide_number}: {str(e)}", created_files, slides_info

    def _handle_finalize(
        self,
        project_id: str,
        job_id: str,
        source_id: str,
        tool_input: Dict[str, Any],
        created_files: List[str],
        slides_info: List[Dict[str, Any]],
        iterations: int,
        input_tokens: int,
        output_tokens: int
    ) -> Dict[str, Any]:
        """Handle finalize_presentation tool call (termination)."""
        summary = tool_input.get("summary", "")
        total_slides = tool_input.get("total_slides", 0)
        slides_created = tool_input.get("slides_created", [])
        design_notes = tool_input.get("design_notes", "")

        print(f"      Finalizing presentation ({total_slides} slides)")

        try:
            job = studio_index_service.get_presentation_job(project_id, job_id)
            title = job.get("presentation_title", "Presentation") if job else "Presentation"

            # Get list of slide files in order
            slide_files = sorted([
                f for f in created_files
                if f.startswith("slide_") and f.endswith(".html")
            ])

            studio_index_service.update_presentation_job(
                project_id, job_id,
                status="ready",
                status_message="Presentation generated! Ready for export.",
                files=created_files,
                slide_files=slide_files,
                slides_metadata=slides_created,
                summary=summary,
                design_notes=design_notes,
                total_slides=len(slide_files),
                preview_url=f"/api/v1/projects/{project_id}/studio/presentations/{job_id}/preview",
                download_url=f"/api/v1/projects/{project_id}/studio/presentations/{job_id}/download",
                iterations=iterations,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                completed_at=datetime.now().isoformat()
            )

            return {
                "success": True,
                "job_id": job_id,
                "presentation_title": title,
                "total_slides": len(slide_files),
                "slide_files": slide_files,
                "files": created_files,
                "summary": summary,
                "preview_url": f"/api/v1/projects/{project_id}/studio/presentations/{job_id}/preview",
                "download_url": f"/api/v1/projects/{project_id}/studio/presentations/{job_id}/download",
                "iterations": iterations,
                "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens}
            }

        except Exception as e:
            error_msg = f"Error finalizing presentation: {str(e)}"
            print(f"      {error_msg}")

            studio_index_service.update_presentation_job(
                project_id, job_id,
                status="error",
                error_message=error_msg
            )

            return {
                "success": False,
                "error_message": error_msg,
                "iterations": iterations,
                "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens}
            }


# Singleton instance
presentation_tool_executor = PresentationToolExecutor()
