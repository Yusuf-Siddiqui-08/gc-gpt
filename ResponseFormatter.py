import re
import markdown
from io import StringIO
from pygments.lexers import PythonLexer, get_lexer_by_name
from pygments.util import ClassNotFound
from TagFormatter import TagFormatter


class ResponseFormatter:
    """Formats AI responses by converting markdown to HTML with support for tables, LaTeX, code blocks, etc."""

    @staticmethod
    def format(text: str) -> str:
        """Format AI response by converting markdown to HTML with support for tables, LaTeX, code blocks, etc."""
        if not text:
            return text

        # Protect LaTeX equations and code blocks by replacing them with placeholders
        latex_blocks = []
        code_blocks = []

        def save_latex_display(match):
            """Save display math equations \\[ ... \\] or $$ ... $$"""
            latex_blocks.append(('display', match.group(1)))
            # Use HTML comments as placeholders to survive markdown processing
            return f"<!--LATEX_DISPLAY_{len(latex_blocks) - 1}-->"

        def save_latex_inline(match):
            """Save inline math equations \\( ... \\) or $ ... $"""
            latex_blocks.append(('inline', match.group(1)))
            return f"<!--LATEX_INLINE_{len(latex_blocks) - 1}-->"

        def save_code_block(match):
            """Save code blocks for syntax highlighting."""
            lang = match.group(1) or ''
            code = match.group(2).strip()
            code_blocks.append((lang.strip().lower(), code))
            return f"\n\n<!--CODE_BLOCK_{len(code_blocks) - 1}-->\n\n"

        # Match and save fenced code blocks BEFORE LaTeX processing
        # Pattern matches: ```lang (optional newline) code (optional newline) ```
        text = re.sub(r'```(\w*)\s*\n(.*?)```', save_code_block, text, flags=re.DOTALL)

        # Match and save LaTeX display equations: \[ ... \] or $$ ... $$
        text = re.sub(r'\\\[(.*?)\\\]', save_latex_display, text, flags=re.DOTALL)
        text = re.sub(r'\$\$(.*?)\$\$', save_latex_display, text, flags=re.DOTALL)

        # Match and save inline equations: \( ... \) or $ ... $
        text = re.sub(r'\\\((.*?)\\\)', save_latex_inline, text, flags=re.DOTALL)
        text = re.sub(r'(?<!\$)\$(?!\$)([^$\n]+?)\$', save_latex_inline, text)

        # Use markdown library WITHOUT fenced_code extension since we're handling it manually
        html = markdown.markdown(
            text,
            extensions=[
                'tables',     # Table support
                'nl2br',      # Convert newlines to <br> tags
                'sane_lists', # Better list handling
            ]
        )

        # Add styling to tables
        html = html.replace('<table>', '<table style="border-collapse: collapse; width: 100%; margin: 10px 0; border: 1px solid #ddd;">')
        html = html.replace('<th>', '<th style="border: 1px solid #ddd; padding: 8px; background-color: #f2f2f2; text-align: left; color: #000;">')
        html = html.replace('<td>', '<td style="border: 1px solid #ddd; padding: 8px;">')

        # Add styling to inline code (not code blocks, those are handled separately)
        html = html.replace('<code>', '<code style="background-color: #2d2d2d; color: #e5e7eb; padding: 2px 6px; border-radius: 4px; font-family: \'Consolas\', \'Monaco\', \'Courier New\', monospace; font-size: 0.9em;">')

        # Add styling to headers
        html = html.replace('<h1>', '<h1 style="margin-top: 20px; margin-bottom: 10px; font-size: 2em; font-weight: bold;">')
        html = html.replace('<h2>', '<h2 style="margin-top: 18px; margin-bottom: 8px; font-size: 1.5em; font-weight: bold;">')
        html = html.replace('<h3>', '<h3 style="margin-top: 16px; margin-bottom: 6px; font-size: 1.25em; font-weight: bold;">')
        html = html.replace('<h4>', '<h4 style="margin-top: 14px; margin-bottom: 4px; font-size: 1.1em; font-weight: bold;">')

        # Add styling to horizontal rules
        html = html.replace('<hr />', '<hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;" />')
        html = html.replace('<hr>', '<hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">')

        # Add styling to lists
        html = html.replace('<ul>', '<ul style="margin: 10px 0; padding-left: 20px;">')
        html = html.replace('<ol>', '<ol style="margin: 10px 0; padding-left: 20px;">')
        html = html.replace('<li>', '<li style="margin: 4px 0;">')

        # Add target="_blank" to all links
        html = re.sub(r'<a href="([^"]*)">', r'<a href="\1" target="_blank" rel="noopener noreferrer">', html)

        # Proxy external images to bypass CORS and referrer policies
        def proxy_image(match):
            img_tag = match.group(0)
            # Extract src attribute
            src_match = re.search(r'src="([^"]*)"', img_tag)
            if src_match:
                original_src = src_match.group(1)
                # Use wsrv.nl image proxy (free, fast, and reliable)
                proxied_src = f"https://wsrv.nl/?url={original_src}"
                img_tag = img_tag.replace(f'src="{original_src}"', f'src="{proxied_src}"')
            # Add styling and error handling
            if 'style=' not in img_tag:
                img_tag = img_tag.replace('<img ', '<img style="max-width: 100%; height: auto; display: block; margin: 10px 0;" ')
            if 'onerror=' not in img_tag:
                img_tag = img_tag.replace('<img ', '<img onerror="this.style.display=\'none\'" ')
            return img_tag

        html = re.sub(r'<img\s+[^>]*>', proxy_image, html)

        # Restore LaTeX equations with proper delimiters for MathJax/KaTeX
        for i, (latex_type, latex_content) in enumerate(latex_blocks):
            if latex_type == 'display':
                # Use display math delimiters that MathJax/KaTeX will recognize
                placeholder = f"<!--LATEX_DISPLAY_{i}-->"
                latex_html = f'<div class="math-display" style="margin: 15px 0; text-align: center; overflow-x: auto;">\\[{latex_content}\\]</div>'
                html = html.replace(placeholder, latex_html)
            else:  # inline
                # Use inline math delimiters
                placeholder = f"<!--LATEX_INLINE_{i}-->"
                latex_html = f'<span class="math-inline">\\({latex_content}\\)</span>'
                html = html.replace(placeholder, latex_html)

        # Restore code blocks with syntax highlighting
        for i, (lang, code) in enumerate(code_blocks):
            placeholder = f"<!--CODE_BLOCK_{i}-->"

            # Try to apply syntax highlighting if language is specified
            highlighted_code = code
            if lang:
                try:
                    lexer = get_lexer_by_name(lang, stripall=True)
                    output = StringIO()
                    TagFormatter().format(lexer.get_tokens(code), output)
                    highlighted_code = output.getvalue()
                except ClassNotFound:
                    # Language not found, use plain text with HTML escaping
                    highlighted_code = ResponseFormatter._escape_html(code)
            else:
                # No language specified, try to detect if it's Python
                if any(keyword in code for keyword in ['def ', 'class ', 'import ', 'print(', 'from ', 'return ']):
                    try:
                        output = StringIO()
                        TagFormatter().format(PythonLexer().get_tokens(code), output)
                        highlighted_code = output.getvalue()
                    except Exception:
                        highlighted_code = ResponseFormatter._escape_html(code)
                else:
                    highlighted_code = ResponseFormatter._escape_html(code)

            code_html = f'<pre style="background-color: #2d2d2d; color: #e5e7eb; padding: 14px; border-radius: 6px; overflow-x: auto; margin: 12px 0; border: 1px solid rgba(255,255,255,0.1);"><code style="background: transparent; color: inherit; padding: 0; font-family: \'Consolas\', \'Monaco\', \'Courier New\', monospace; font-size: 0.9em;">{highlighted_code}</code></pre>'

            # Replace placeholder even if it's wrapped in <p> tags
            html = html.replace(placeholder, code_html)
            html = html.replace(f'<p>{placeholder}</p>', code_html)
            html = re.sub(rf'<p>\s*{re.escape(placeholder)}\s*</p>', code_html, html)

        return html

    @staticmethod
    def _escape_html(text):
        """Escape HTML special characters."""
        return (text.replace('&', '&amp;')
                    .replace('<', '&lt;')
                    .replace('>', '&gt;')
                    .replace('"', '&quot;')
                    .replace("'", '&#39;'))
