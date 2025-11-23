// Icon components for AI models using @lobehub/icons-static-svg from CDN
// Using React.createElement for compatibility with the browser-based JSX transpiler

const CDN_BASE = 'https://unpkg.com/@lobehub/icons-static-svg@latest/icons';

const IconWrapper = ({ children, size = 24, style, ...props }) => {
  return React.createElement('span', {
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      width: size,
      height: size,
      ...style
    },
    ...props
  }, children);
};

// Generic CDN Icon Component
const CDNIcon = ({ slug, size = 24, alt, ...props }) => {
  return React.createElement(IconWrapper, { size, ...props },
    React.createElement('img', {
      src: `${CDN_BASE}/${slug}.svg`,
      alt: alt || slug,
      width: size,
      height: size,
      style: {
        display: 'block',
        width: '100%',
        height: '100%',
        objectFit: 'contain'
      }
    })
  );
};

// OpenAI Icon from LobeHub
export const OpenAI = ({ size = 24, ...props }) => {
  return React.createElement(CDNIcon, {
    slug: 'openai',
    size,
    alt: 'OpenAI',
    ...props
  });
};

// DeepSeek Icon from LobeHub
export const DeepSeek = ({ size = 24, ...props }) => {
  return React.createElement(CDNIcon, {
    slug: 'deepseek',
    size,
    alt: 'DeepSeek',
    ...props
  });
};

// Qwen Icon from LobeHub
export const Qwen = ({ size = 24, ...props }) => {
  return React.createElement(CDNIcon, {
    slug: 'qwen',
    size,
    alt: 'Qwen',
    ...props
  });
};

// GLMV Icon (ChatGLM) from LobeHub
export const GLMV = ({ size = 24, ...props }) => {
  return React.createElement(CDNIcon, {
    slug: 'chatglm',
    size,
    alt: 'ChatGLM',
    ...props
  });
};

// Kimi Icon from LobeHub
export const Kimi = ({ size = 24, ...props }) => {
  return React.createElement(CDNIcon, {
    slug: 'kimi',
    size,
    alt: 'Kimi',
    ...props
  });
};

// Export IconMap
export const IconMap = {
  OpenAI,
  DeepSeek,
  Qwen,
  GLMV,
  Kimi,
};
