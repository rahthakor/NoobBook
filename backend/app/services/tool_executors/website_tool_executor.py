"""
Website Tool Executor - Handles tool execution for website agent.

Executes: plan_website, generate_website_image, read_file, create_file,
          update_file_lines, insert_code, finalize_website
"""

from typing import Dict, Any, List, Tuple
from datetime import datetime
from pathlib import Path

from app.services.integrations.google import imagen_service
from app.services.studio_services import studio_index_service
from app.utils.path_utils import get_studio_dir


class WebsiteToolExecutor:
    """Executes website agent tools."""

    TERMINATION_TOOL = "finalize_website"

    def execute_tool(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], bool]:
        """
        Execute a website tool.

        Args:
            tool_name: Name of the tool to execute
            tool_input: Tool input parameters
            context: Execution context (project_id, job_id, generated_images, etc.)

        Returns:
            Tuple of (result_dict, is_termination)
        """
        project_id = context["project_id"]
        job_id = context["job_id"]

        if tool_name == "plan_website":
            result = self._execute_plan_website(project_id, job_id, tool_input)
            return {"success": True, "message": result}, False

        elif tool_name == "generate_website_image":
            result = self._execute_generate_image(
                project_id, job_id, tool_input, context["generated_images"]
            )
            return {"success": True, "message": result}, False

        elif tool_name == "read_file":
            result = self._execute_read_file(project_id, job_id, tool_input)
            return {"success": True, "message": result}, False

        elif tool_name == "create_file":
            result = self._execute_create_file(
                project_id, job_id, tool_input, context["created_files"]
            )
            return {"success": True, "message": result}, False

        elif tool_name == "update_file_lines":
            result = self._execute_update_file_lines(project_id, job_id, tool_input)
            return {"success": True, "message": result}, False

        elif tool_name == "insert_code":
            result = self._execute_insert_code(project_id, job_id, tool_input)
            return {"success": True, "message": result}, False

        elif tool_name == "finalize_website":
            result = self._execute_finalize_website(
                project_id, job_id, tool_input, context
            )
            return result, True

        else:
            return {"success": False, "error": f"Unknown tool: {tool_name}"}, False

    def _execute_plan_website(
        self,
        project_id: str,
        job_id: str,
        tool_input: Dict[str, Any]
    ) -> str:
        """Execute plan_website tool."""
        site_name = tool_input.get("site_name", "Unnamed Website")
        pages = tool_input.get("pages", [])

        print(f"      Planning: {site_name} ({len(pages)} pages)")

        studio_index_service.update_website_job(
            project_id, job_id,
            site_type=tool_input.get("site_type"),
            site_name=site_name,
            pages=pages,
            features=tool_input.get("features"),
            design_system=tool_input.get("design_system"),
            navigation_style=tool_input.get("navigation_style"),
            images_needed=tool_input.get("images_needed", []),
            layout_notes=tool_input.get("layout_notes"),
            status_message=f"Planned {len(pages)}-page website, generating images..."
        )

        return f"Website plan saved successfully. Site: '{site_name}', Type: {tool_input.get('site_type')}, Pages: {len(pages)}, Features: {len(tool_input.get('features', []))}"

    def _execute_generate_image(
        self,
        project_id: str,
        job_id: str,
        tool_input: Dict[str, Any],
        generated_images: List[Dict[str, str]]
    ) -> str:
        """Execute generate_website_image tool."""
        purpose = tool_input.get("purpose", "unknown")
        image_prompt = tool_input.get("image_prompt", "")
        aspect_ratio = tool_input.get("aspect_ratio", "16:9")

        print(f"      Generating image for: {purpose}")

        studio_index_service.update_website_job(
            project_id, job_id,
            status_message=f"Generating image for {purpose}..."
        )

        try:
            studio_dir = get_studio_dir(project_id)
            website_dir = Path(studio_dir) / "websites" / job_id / "assets"
            website_dir.mkdir(parents=True, exist_ok=True)

            image_index = len(generated_images) + 1
            filename_prefix = f"{job_id}_image_{image_index}"

            image_result = imagen_service.generate_images(
                prompt=image_prompt,
                output_dir=website_dir,
                num_images=1,
                filename_prefix=filename_prefix,
                aspect_ratio=aspect_ratio
            )

            if not image_result.get("success") or not image_result.get("images"):
                return f"Error generating image for {purpose}: {image_result.get('error', 'Unknown error')}"

            image_data = image_result["images"][0]
            filename = image_data["filename"]

            image_info = {
                "purpose": purpose,
                "filename": filename,
                "placeholder": f"IMAGE_{image_index}",
                "url": f"/api/v1/projects/{project_id}/studio/websites/{job_id}/assets/{filename}"
            }
            generated_images.append(image_info)

            studio_index_service.update_website_job(
                project_id, job_id,
                images=generated_images
            )

            print(f"      Saved: {filename}")

            return f"Image generated successfully for '{purpose}'. Use placeholder '{image_info['placeholder']}' in your HTML code for this image."

        except Exception as e:
            error_msg = f"Error generating image for {purpose}: {str(e)}"
            print(f"      {error_msg}")
            return error_msg

    def _execute_read_file(
        self,
        project_id: str,
        job_id: str,
        tool_input: Dict[str, Any]
    ) -> str:
        """Execute read_file tool with smart context awareness."""
        filename = tool_input.get("filename")
        start_line = tool_input.get("start_line")
        end_line = tool_input.get("end_line")

        print(f"      Reading: {filename}" + (f" (lines {start_line}-{end_line})" if start_line else ""))

        website_dir = Path(get_studio_dir(project_id)) / "websites" / job_id
        file_path = website_dir / filename

        if not file_path.exists():
            return f"Error: File '{filename}' does not exist yet. Use create_file to create it first."

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            total_lines = len(lines)

            # Small file: return all
            if total_lines < 100:
                content = "".join(lines)
                return f"File: {filename} ({total_lines} lines)\n\n{content}"

            # Large file, no range: return overview
            if start_line is None:
                first_50 = "".join(lines[:50])
                last_50 = "".join(lines[-50:])
                omitted_count = total_lines - 100
                return f"File: {filename} ({total_lines} lines)\n\n[Lines 1-50]\n{first_50}\n\n... [{omitted_count} lines omitted] ...\n\n[Lines {total_lines-49}-{total_lines}]\n{last_50}"

            # Specific range with context
            context_start = max(0, start_line - 1 - 5)
            context_end = min(total_lines, (end_line if end_line else total_lines) + 5)

            content = "".join(lines[context_start:context_end])
            return f"File: {filename} (lines {context_start+1}-{context_end} of {total_lines})\n\n{content}"

        except Exception as e:
            return f"Error reading file '{filename}': {str(e)}"

    def _execute_create_file(
        self,
        project_id: str,
        job_id: str,
        tool_input: Dict[str, Any],
        created_files: List[str]
    ) -> str:
        """Execute create_file tool."""
        filename = tool_input.get("filename")
        content = tool_input.get("content", "")

        print(f"      Creating: {filename} ({len(content)} chars)")

        try:
            website_dir = Path(get_studio_dir(project_id)) / "websites" / job_id
            website_dir.mkdir(parents=True, exist_ok=True)

            file_path = website_dir / filename

            # Replace IMAGE_N placeholders with actual URLs
            final_content = self._replace_image_placeholders(
                content, project_id, job_id
            )

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(final_content)

            line_count = len(final_content.split('\n'))
            char_count = len(final_content)

            if filename not in created_files:
                created_files.append(filename)

            studio_index_service.update_website_job(
                project_id, job_id,
                files=created_files,
                status_message=f"Created {filename} ({len(created_files)} files so far)"
            )

            print(f"      Saved: {filename}")

            return f"File '{filename}' created successfully ({line_count} lines, {char_count} characters)"

        except Exception as e:
            return f"Error creating file '{filename}': {str(e)}"

    def _execute_update_file_lines(
        self,
        project_id: str,
        job_id: str,
        tool_input: Dict[str, Any]
    ) -> str:
        """Execute update_file_lines tool."""
        filename = tool_input.get("filename")
        start_line = tool_input.get("start_line")
        end_line = tool_input.get("end_line")
        new_content = tool_input.get("new_content", "")

        print(f"      Updating: {filename} lines {start_line}-{end_line}")

        website_dir = Path(get_studio_dir(project_id)) / "websites" / job_id
        file_path = website_dir / filename

        if not file_path.exists():
            return f"Error: File '{filename}' does not exist. Use create_file first."

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            if start_line < 1 or end_line > len(lines):
                return f"Error: Invalid line range. File has {len(lines)} lines, you requested {start_line}-{end_line}."

            # Replace IMAGE_N placeholders
            final_new_content = self._replace_image_placeholders(
                new_content, project_id, job_id
            )

            # Replace lines (convert to 0-indexed)
            new_lines = final_new_content.split('\n')
            lines[start_line-1:end_line] = [line + '\n' for line in new_lines]

            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)

            return f"Updated lines {start_line}-{end_line} in '{filename}'"

        except Exception as e:
            return f"Error updating file '{filename}': {str(e)}"

    def _execute_insert_code(
        self,
        project_id: str,
        job_id: str,
        tool_input: Dict[str, Any]
    ) -> str:
        """Execute insert_code tool."""
        filename = tool_input.get("filename")
        after_line = tool_input.get("after_line")
        content = tool_input.get("content", "")

        print(f"      Inserting: {filename} after line {after_line}")

        website_dir = Path(get_studio_dir(project_id)) / "websites" / job_id
        file_path = website_dir / filename

        if not file_path.exists():
            return f"Error: File '{filename}' does not exist. Use create_file first."

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            if after_line < 0 or after_line > len(lines):
                return f"Error: Invalid line number. File has {len(lines)} lines, you requested to insert after line {after_line}."

            # Replace IMAGE_N placeholders
            final_content = self._replace_image_placeholders(
                content, project_id, job_id
            )

            new_lines = [line + '\n' for line in final_content.split('\n')]
            lines[after_line:after_line] = new_lines

            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)

            return f"Inserted {len(new_lines)} lines after line {after_line} in '{filename}'"

        except Exception as e:
            return f"Error inserting code in '{filename}': {str(e)}"

    def _execute_finalize_website(
        self,
        project_id: str,
        job_id: str,
        tool_input: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute finalize_website tool (termination)."""
        summary = tool_input.get("summary", "")
        pages_created = tool_input.get("pages_created", [])
        features_implemented = tool_input.get("features_implemented", [])
        cdn_libraries = tool_input.get("cdn_libraries_used", [])

        generated_images = context["generated_images"]
        created_files = context["created_files"]
        iterations = context["iterations"]
        input_tokens = context["input_tokens"]
        output_tokens = context["output_tokens"]

        print(f"      Finalizing website ({len(pages_created)} pages)")

        try:
            job = studio_index_service.get_website_job(project_id, job_id)
            site_name = job.get("site_name", "Website")

            studio_index_service.update_website_job(
                project_id, job_id,
                status="ready",
                status_message="Website generated successfully!",
                files=created_files,
                pages_created=pages_created,
                features_implemented=features_implemented,
                cdn_libraries_used=cdn_libraries,
                summary=summary,
                preview_url=f"/api/v1/projects/{project_id}/studio/websites/{job_id}/preview",
                download_url=f"/api/v1/projects/{project_id}/studio/websites/{job_id}/download",
                iterations=iterations,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                completed_at=datetime.now().isoformat()
            )

            return {
                "success": True,
                "job_id": job_id,
                "site_name": site_name,
                "pages_created": pages_created,
                "files": created_files,
                "images": generated_images,
                "features": features_implemented,
                "cdn_libraries": cdn_libraries,
                "summary": summary,
                "preview_url": f"/api/v1/projects/{project_id}/studio/websites/{job_id}/preview",
                "download_url": f"/api/v1/projects/{project_id}/studio/websites/{job_id}/download",
                "iterations": iterations,
                "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens}
            }

        except Exception as e:
            error_msg = f"Error finalizing website: {str(e)}"
            print(f"      {error_msg}")

            studio_index_service.update_website_job(
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

    def _replace_image_placeholders(
        self,
        content: str,
        project_id: str,
        job_id: str
    ) -> str:
        """Replace IMAGE_N placeholders with actual URLs."""
        job = studio_index_service.get_website_job(project_id, job_id)
        images = job.get("images", [])

        result = content
        for image_info in images:
            placeholder = image_info["placeholder"]
            actual_url = image_info["url"]
            result = result.replace(f'"{placeholder}"', f'"{actual_url}"')
            result = result.replace(f"'{placeholder}'", f"'{actual_url}'")
            result = result.replace(f'src={placeholder}', f'src="{actual_url}"')

        return result


# Singleton instance
website_tool_executor = WebsiteToolExecutor()
