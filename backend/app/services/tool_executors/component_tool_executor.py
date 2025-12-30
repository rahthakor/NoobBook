"""
Component Tool Executor - Handles tool execution for component agent.

Tool handlers extracted from component_agent_service.py for separation of concerns.
Agent handles orchestration, executor handles tool-specific logic.
"""

from typing import Dict, Any, Tuple
from datetime import datetime
from pathlib import Path

from app.utils.path_utils import get_studio_dir
from app.services.studio_services import studio_index_service


class ComponentToolExecutor:
    """Executes component agent tools."""

    TERMINATION_TOOL = "write_component_code"

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
            context: Execution context (project_id, job_id, etc.)

        Returns:
            Tuple of (result_dict, is_termination)
        """
        project_id = context["project_id"]
        job_id = context["job_id"]

        if tool_name == "plan_components":
            result = self._handle_plan(project_id, job_id, tool_input)
            return {"success": True, "message": result}, False

        elif tool_name == "write_component_code":
            result = self._handle_write_code(
                project_id=project_id,
                job_id=job_id,
                tool_input=tool_input,
                iterations=context.get("iterations", 0),
                input_tokens=context.get("input_tokens", 0),
                output_tokens=context.get("output_tokens", 0)
            )
            return result, True  # Termination

        else:
            return {"success": False, "message": f"Unknown tool: {tool_name}"}, False

    def _handle_plan(
        self,
        project_id: str,
        job_id: str,
        tool_input: Dict[str, Any]
    ) -> str:
        """Handle plan_components tool call."""
        component_category = tool_input.get("component_category", "other")
        component_description = tool_input.get("component_description", "")
        variations = tool_input.get("variations", [])

        print(f"      Planning: {component_category} ({len(variations)} variations)")

        # Update job with plan
        studio_index_service.update_component_job(
            project_id, job_id,
            component_category=component_category,
            component_description=component_description,
            variations_planned=variations,
            technical_notes=tool_input.get("technical_notes"),
            status_message=f"Planned {len(variations)} variations, generating code..."
        )

        variation_names = [v.get("variation_name", "Unnamed") for v in variations]
        return f"Component plan saved successfully. Category: {component_category}, Variations: {', '.join(variation_names)}"

    def _handle_write_code(
        self,
        project_id: str,
        job_id: str,
        tool_input: Dict[str, Any],
        iterations: int,
        input_tokens: int,
        output_tokens: int
    ) -> Dict[str, Any]:
        """Handle write_component_code tool call (termination)."""
        components = tool_input.get("components", [])
        usage_notes = tool_input.get("usage_notes", "")

        print(f"      Writing code for {len(components)} components")

        try:
            # Prepare output directory
            studio_dir = get_studio_dir(project_id)
            component_dir = Path(studio_dir) / "components" / job_id
            component_dir.mkdir(parents=True, exist_ok=True)

            # Save each component as HTML file
            saved_components = []
            for idx, component in enumerate(components):
                variation_name = component.get("variation_name", f"Variation {idx + 1}")
                html_code = component.get("html_code", "")
                description = component.get("description", "")

                # Create safe filename
                safe_name = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in variation_name)
                safe_name = safe_name.replace(' ', '_').lower()
                filename = f"{safe_name}.html"

                # Save HTML file
                file_path = component_dir / filename
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(html_code)

                print(f"      Saved: {filename}")

                # Track component
                saved_components.append({
                    "variation_name": variation_name,
                    "filename": filename,
                    "description": description,
                    "preview_url": f"/api/v1/projects/{project_id}/studio/components/{job_id}/preview/{filename}",
                    "char_count": len(html_code)
                })

            # Get job info for component category
            job = studio_index_service.get_component_job(project_id, job_id)
            component_category = job.get("component_category", "component") if job else "component"
            component_description = job.get("component_description", "") if job else ""

            # Update job to ready
            studio_index_service.update_component_job(
                project_id, job_id,
                status="ready",
                status_message="Components generated successfully!",
                components=saved_components,
                usage_notes=usage_notes,
                iterations=iterations,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                completed_at=datetime.now().isoformat()
            )

            return {
                "success": True,
                "job_id": job_id,
                "component_category": component_category,
                "component_description": component_description,
                "components": saved_components,
                "usage_notes": usage_notes,
                "iterations": iterations,
                "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens}
            }

        except Exception as e:
            error_msg = f"Error writing component code: {str(e)}"
            print(f"      {error_msg}")

            studio_index_service.update_component_job(
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
component_tool_executor = ComponentToolExecutor()
