from pygments.formatter import Formatter


class TagFormatter(Formatter):
    """Custom Pygments formatter that outputs HTML with inline color styling."""

    def format(self, tokensource, outfile):
        from pygments.token import Token, string_to_tokentype, STANDARD_TYPES

        for ttype, value in tokensource:
            color = None

            # Check token type hierarchy - tokens are tuples that can be compared
            # Use string representation for easier matching
            ttype_str = str(ttype)

            # Match in order of specificity (most specific first)
            if 'Keyword' in ttype_str:
                color = '#ff7b72'  # Keywords - coral red
            elif 'Name.Function' in ttype_str:
                color = '#d2a8ff'  # Function names - purple
            elif 'Name.Class' in ttype_str:
                color = '#79c0ff'  # Class names - light blue
            elif 'Name.Builtin' in ttype_str:
                color = '#79c0ff'  # Built-in functions - light blue
            elif 'String' in ttype_str or 'Literal.String' in ttype_str:
                color = '#a5d6ff'  # Strings - light cyan
            elif 'Number' in ttype_str or 'Literal.Number' in ttype_str:
                color = '#79c0ff'  # Numbers - light blue
            elif 'Comment' in ttype_str:
                color = '#8b949e'  # Comments - gray
            elif 'Operator' in ttype_str:
                color = '#ff7b72'  # Operators - coral red
            elif 'Name' in ttype_str:
                color = '#e5e7eb'  # General names - light gray

            if color:
                # Use !important to override any frontend CSS
                outfile.write(f'<span style="color: {color} !important;">{self._escape_html(value)}</span>')
            else:
                outfile.write(self._escape_html(value))

    def _escape_html(self, text):
        """Escape HTML special characters."""
        return (text.replace('&', '&amp;')
                    .replace('<', '&lt;')
                    .replace('>', '&gt;')
                    .replace('"', '&quot;')
                    .replace("'", '&#39;'))
