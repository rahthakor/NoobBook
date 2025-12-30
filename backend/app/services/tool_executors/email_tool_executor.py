"""
Email Tool Executor - Handles tool execution for email agent.

Tool handlers extracted from email_agent_service.py for separation of concerns.
Agent handles orchestration, executor handles tool-specific logic.
"""

import os
from typing import Dict, Any, Tuple, List
from datetime import datetime
from pathlib import Path

from app.utils.path_utils import get_studio_dir
from app.services.studio_services import studio_index_service
from app.services.integrations.google import imagen_service


class EmailToolExecutor:
    """Executes email agent tools."""

    TERMINATION_TOOL = "write_email_code"

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
            context: Execution context (project_id, job_id, generated_images, etc.)

        Returns:
            Tuple of (result_dict, is_termination)
        """
        project_id = context["project_id"]
        job_id = context["job_id"]

        if tool_name == "plan_email_template":
            result = self._handle_plan(project_id, job_id, tool_input)
            return {"success": True, "message": result}, False

        elif tool_name == "generate_email_image":
            generated_images = context.get("generated_images", [])
            result, image_info = self._handle_generate_image(
                project_id, job_id, tool_input, generated_images
            )
            return {"success": True, "message": result, "image_info": image_info}, False

        elif tool_name == "write_email_code":
            result = self._handle_write_code(
                project_id=project_id,
                job_id=job_id,
                tool_input=tool_input,
                generated_images=context.get("generated_images", []),
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
        """Handle plan_email_template tool call."""
        template_name = tool_input.get("template_name", "Unnamed")
        template_type = tool_input.get("template_type")
        sections = tool_input.get("sections", [])

        print(f"      Planning: {template_name}")

        # Update job with plan
        studio_index_service.update_email_job(
            project_id, job_id,
            template_name=template_name,
            template_type=template_type,
            color_scheme=tool_input.get("color_scheme"),
            sections=sections,
            layout_notes=tool_input.get("layout_notes"),
            status_message="Template planned, generating images..."
        )

        return (
            f"Template plan saved successfully. "
            f"Template name: '{template_name}', "
            f"Type: {template_type}, "
            f"Sections: {len(sections)}"
        )

    def _handle_generate_image(
        self,
        project_id: str,
        job_id: str,
        tool_input: Dict[str, Any],
        generated_images: List[Dict[str, str]]
    ) -> Tuple[str, Dict[str, str]]:
        """
        Handle generate_email_image tool call.

        Returns:
            Tuple of (result_message, image_info_dict or None)
        """
        section_name = tool_input.get("section_name", "unknown")
        image_prompt = tool_input.get("image_prompt", "")
        aspect_ratio = tool_input.get("aspect_ratio", "16:9")

        print(f"      Generating image for: {section_name}")

        # Update status
        studio_index_service.update_email_job(
            project_id, job_id,
            status_message=f"Generating image for {section_name}..."
        )

        try:
            # Prepare output directory
            studio_dir = get_studio_dir(project_id)
            email_dir = Path(studio_dir) / "email_templates"
            email_dir.mkdir(parents=True, exist_ok=True)

            # Create filename prefix
            image_index = len(generated_images) + 1
            filename_prefix = f"{job_id}_image_{image_index}"

            # Generate image via Gemini
            image_result = imagen_service.generate_images(
                prompt=image_prompt,
                output_dir=email_dir,
                num_images=1,
                filename_prefix=filename_prefix,
                aspect_ratio=aspect_ratio
            )

            if not image_result.get("success") or not image_result.get("images"):
                error_msg = f"Error generating image for {section_name}: {image_result.get('error', 'Unknown error')}"
                return error_msg, None

            # Get the generated image info
            image_data = image_result["images"][0]
            filename = image_data["filename"]

            # Build image info
            image_info = {
                "section_name": section_name,
                "filename": filename,
                "placeholder": f"IMAGE_{image_index}",
                "url": f"/api/v1/projects/{project_id}/studio/email-templates/{filename}"
            }

            # Update job with new image list
            updated_images = generated_images + [image_info]
            studio_index_service.update_email_job(
                project_id, job_id,
                images=updated_images
            )

            print(f"      Saved: {filename}")

            result_msg = (
                f"Image generated successfully for '{section_name}'. "
                f"Use placeholder '{image_info['placeholder']}' in your HTML code for this image."
            )
            return result_msg, image_info

        except Exception as e:
            error_msg = f"Error generating image for {section_name}: {str(e)}"
            print(f"      {error_msg}")
            return error_msg, None

    def _handle_write_code(
        self,
        project_id: str,
        job_id: str,
        tool_input: Dict[str, Any],
        generated_images: List[Dict[str, str]],
        iterations: int,
        input_tokens: int,
        output_tokens: int
    ) -> Dict[str, Any]:
        """Handle write_email_code tool call (termination)."""
        html_code = tool_input.get("html_code", "")
        subject_line = tool_input.get("subject_line_suggestion", "")
        preheader_text = tool_input.get("preheader_text", "")

        print(f"      Writing HTML code ({len(html_code)} chars)")

        try:
            # Replace IMAGE_N placeholders with actual URLs
            final_html = html_code
            for image_info in generated_images:
                placeholder = image_info["placeholder"]
                actual_url = image_info["url"]
                final_html = final_html.replace(f'"{placeholder}"', f'"{actual_url}"')
                final_html = final_html.replace(f"'{placeholder}'", f"'{actual_url}'")

            # Save HTML file
            studio_dir = get_studio_dir(project_id)
            email_dir = os.path.join(studio_dir, "email_templates")
            os.makedirs(email_dir, exist_ok=True)

            html_filename = f"{job_id}.html"
            html_path = os.path.join(email_dir, html_filename)

            with open(html_path, "w", encoding="utf-8") as f:
                f.write(final_html)

            print(f"      Saved: {html_filename}")

            # Get job info for template_name
            job = studio_index_service.get_email_job(project_id, job_id)
            template_name = job.get("template_name", "Email Template") if job else "Email Template"

            # Update job to ready
            studio_index_service.update_email_job(
                project_id, job_id,
                status="ready",
                status_message="Email template generated successfully!",
                html_file=html_filename,
                html_url=f"/api/v1/projects/{project_id}/studio/email-templates/{html_filename}",
                preview_url=f"/api/v1/projects/{project_id}/studio/email-templates/{job_id}/preview",
                subject_line=subject_line,
                preheader_text=preheader_text,
                iterations=iterations,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                completed_at=datetime.now().isoformat()
            )

            return {
                "success": True,
                "job_id": job_id,
                "template_name": template_name,
                "html_file": html_filename,
                "html_url": f"/api/v1/projects/{project_id}/studio/email-templates/{html_filename}",
                "preview_url": f"/api/v1/projects/{project_id}/studio/email-templates/{job_id}/preview",
                "images": generated_images,
                "subject_line": subject_line,
                "preheader_text": preheader_text,
                "iterations": iterations,
                "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens}
            }

        except Exception as e:
            error_msg = f"Error saving HTML code: {str(e)}"
            print(f"      {error_msg}")

            studio_index_service.update_email_job(
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
email_tool_executor = EmailToolExecutor()
