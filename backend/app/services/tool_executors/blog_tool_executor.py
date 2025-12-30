"""
Blog Tool Executor - Handles tool execution for blog agent.

Executes: plan_blog_post, generate_blog_image, write_blog_post
"""

import os
from typing import Dict, Any, List, Tuple
from datetime import datetime
from pathlib import Path

from app.services.integrations.google import imagen_service
from app.services.studio_services import studio_index_service
from app.utils.path_utils import get_studio_dir


class BlogToolExecutor:
    """Executes blog agent tools."""

    TERMINATION_TOOL = "write_blog_post"

    def execute_tool(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], bool]:
        """
        Execute a blog tool.

        Args:
            tool_name: Name of the tool to execute
            tool_input: Tool input parameters
            context: Execution context (project_id, job_id, etc.)

        Returns:
            Tuple of (result_dict, is_termination)
        """
        project_id = context["project_id"]
        job_id = context["job_id"]

        if tool_name == "plan_blog_post":
            result = self._execute_plan_blog(project_id, job_id, tool_input)
            return {"success": True, "message": result}, False

        elif tool_name == "generate_blog_image":
            result = self._execute_generate_image(
                project_id, job_id, tool_input, context["generated_images"]
            )
            return {"success": True, "message": result}, False

        elif tool_name == "write_blog_post":
            result = self._execute_write_blog(
                project_id, job_id, tool_input, context
            )
            return result, True

        else:
            return {"success": False, "error": f"Unknown tool: {tool_name}"}, False

    def _execute_plan_blog(
        self,
        project_id: str,
        job_id: str,
        tool_input: Dict[str, Any]
    ) -> str:
        """Execute plan_blog_post tool."""
        title = tool_input.get("title", "Untitled Blog Post")
        outline = tool_input.get("outline", [])

        print(f"      Planning: {title[:50]}...")

        studio_index_service.update_blog_job(
            project_id, job_id,
            title=title,
            meta_description=tool_input.get("meta_description"),
            tone=tool_input.get("tone"),
            outline=outline,
            target_word_count=tool_input.get("estimated_word_count", 3000),
            status_message="Blog planned, generating images..."
        )

        return f"Blog plan saved successfully. Title: '{title}', Sections: {len(outline)}, Target word count: {tool_input.get('estimated_word_count', 3000)}"

    def _execute_generate_image(
        self,
        project_id: str,
        job_id: str,
        tool_input: Dict[str, Any],
        generated_images: List[Dict[str, str]]
    ) -> str:
        """Execute generate_blog_image tool."""
        purpose = tool_input.get("purpose", "unknown")
        section_heading = tool_input.get("section_heading", "")
        image_prompt = tool_input.get("image_prompt", "")
        alt_text = tool_input.get("alt_text", "Blog image")
        aspect_ratio = tool_input.get("aspect_ratio", "16:9")

        print(f"      Generating image for: {purpose}")

        studio_index_service.update_blog_job(
            project_id, job_id,
            status_message=f"Generating image for {purpose}..."
        )

        try:
            studio_dir = get_studio_dir(project_id)
            blog_dir = Path(studio_dir) / "blogs"
            blog_dir.mkdir(parents=True, exist_ok=True)

            image_index = len(generated_images) + 1
            filename_prefix = f"{job_id}_image_{image_index}"

            image_result = imagen_service.generate_images(
                prompt=image_prompt,
                output_dir=blog_dir,
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
                "section_heading": section_heading,
                "filename": filename,
                "placeholder": f"IMAGE_{image_index}",
                "alt_text": alt_text,
                "url": f"/api/v1/projects/{project_id}/studio/blogs/{filename}"
            }
            generated_images.append(image_info)

            studio_index_service.update_blog_job(
                project_id, job_id,
                images=generated_images
            )

            print(f"      Saved: {filename}")

            return f"Image generated successfully for '{purpose}'. Use placeholder 'IMAGE_{image_index}' in your markdown: ![{alt_text}](IMAGE_{image_index})"

        except Exception as e:
            error_msg = f"Error generating image for {purpose}: {str(e)}"
            print(f"      {error_msg}")
            return error_msg

    def _execute_write_blog(
        self,
        project_id: str,
        job_id: str,
        tool_input: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute write_blog_post tool (termination)."""
        markdown_content = tool_input.get("markdown_content", "")
        word_count = tool_input.get("word_count", 0)
        seo_notes = tool_input.get("seo_notes", "")
        generated_images = context["generated_images"]

        print(f"      Writing markdown ({len(markdown_content)} chars, ~{word_count} words)")

        try:
            # Replace IMAGE_N placeholders with actual URLs
            final_markdown = markdown_content
            for image_info in generated_images:
                placeholder = image_info["placeholder"]
                actual_url = image_info["url"]
                final_markdown = final_markdown.replace(f"({placeholder})", f"({actual_url})")
                final_markdown = final_markdown.replace(placeholder, actual_url)

            # Save markdown file
            studio_dir = get_studio_dir(project_id)
            blog_dir = os.path.join(studio_dir, "blogs")
            os.makedirs(blog_dir, exist_ok=True)

            markdown_filename = f"{job_id}.md"
            markdown_path = os.path.join(blog_dir, markdown_filename)

            with open(markdown_path, "w", encoding="utf-8") as f:
                f.write(final_markdown)

            print(f"      Saved: {markdown_filename}")

            # Get job info for title
            job = studio_index_service.get_blog_job(project_id, job_id)
            title = job.get("title", "Blog Post")

            # Update job to ready
            studio_index_service.update_blog_job(
                project_id, job_id,
                status="ready",
                status_message="Blog post generated successfully!",
                markdown_file=markdown_filename,
                markdown_url=f"/api/v1/projects/{project_id}/studio/blogs/{markdown_filename}",
                preview_url=f"/api/v1/projects/{project_id}/studio/blogs/{job_id}/preview",
                word_count=word_count,
                iterations=context["iterations"],
                input_tokens=context["input_tokens"],
                output_tokens=context["output_tokens"],
                completed_at=datetime.now().isoformat()
            )

            return {
                "success": True,
                "job_id": job_id,
                "title": title,
                "markdown_file": markdown_filename,
                "markdown_url": f"/api/v1/projects/{project_id}/studio/blogs/{markdown_filename}",
                "preview_url": f"/api/v1/projects/{project_id}/studio/blogs/{job_id}/preview",
                "images": generated_images,
                "word_count": word_count,
                "target_keyword": context.get("target_keyword", ""),
                "blog_type": context.get("blog_type", ""),
                "seo_notes": seo_notes,
                "iterations": context["iterations"],
                "usage": {
                    "input_tokens": context["input_tokens"],
                    "output_tokens": context["output_tokens"]
                }
            }

        except Exception as e:
            error_msg = f"Error saving blog post: {str(e)}"
            print(f"      {error_msg}")

            studio_index_service.update_blog_job(
                project_id, job_id,
                status="error",
                error_message=error_msg
            )

            return {
                "success": False,
                "error_message": error_msg,
                "iterations": context["iterations"],
                "usage": {
                    "input_tokens": context["input_tokens"],
                    "output_tokens": context["output_tokens"]
                }
            }


# Singleton instance
blog_tool_executor = BlogToolExecutor()
