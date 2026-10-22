import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import Markdown from './Markdown';

describe('Markdown safety', () => {
  it('does not render raw script or event-handler HTML', () => {
    const { container } = render(<Markdown content={'<script>window.pwned = true</script>\n\n<img src=x onerror="alert(1)" />'} />);
    expect(container.querySelector('script')).toBeNull();
    expect(container.querySelector('img')).toBeNull();
  });
  it('removes javascript links and keeps ordinary markdown', () => {
    render(<Markdown content={'[unsafe](javascript:alert(1))\n\n**safe text**'} />);
    expect(screen.getByText('safe text').tagName).toBe('STRONG');
    expect(document.querySelector('a[href^="javascript:"]')).toBeNull();
  });
});
