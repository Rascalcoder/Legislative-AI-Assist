# Legislative AI Assist - Frontend

Modern, responsive frontend for the Competition Law AI Assistant.

## Features

- 🎨 **Modern UI** - Tailwind CSS with custom animations
- 📱 **Responsive** - Works on all devices
- 🚀 **Fast** - Built with Vite for optimal performance
- 🌍 **Multi-language** - Supports SK, HU, EN
- 🔍 **Hybrid Search** - Vector + full-text search interface
- 📄 **Document Management** - Upload and manage legal documents
- 💬 **Chat Interface** - Conversational AI assistant

## Tech Stack

- **Build Tool**: Vite
- **CSS Framework**: Tailwind CSS
- **JavaScript**: Vanilla JS (ES6+)
- **Icons**: SVG (inline)
- **Fonts**: Inter (Google Fonts)

## Quick Start

### Installation

```bash
npm install
```

### Development

```bash
npm run dev
```

Frontend runs on http://localhost:3000 with hot module replacement.

### Production Build

```bash
npm run build
```

Outputs to `dist/` directory.

### Preview Production Build

```bash
npm run preview
```

## Project Structure

```
frontend/
├── index.html              # Main HTML file
├── app.js                  # Application logic
├── styles.css              # Tailwind + custom styles
├── favicon.svg             # Favicon
├── site.webmanifest        # PWA manifest
├── robots.txt              # SEO - robots
├── sitemap.xml             # SEO - sitemap
├── package.json            # Dependencies
├── vite.config.js          # Vite configuration
├── tailwind.config.js      # Tailwind configuration
└── postcss.config.js       # PostCSS configuration
```

## Environment Variables

Create `.env` file:

```bash
API_BASE_URL=http://localhost:8000/api/v1
```

For production, set this in your hosting platform (Vercel/Netlify).

## Deployment

See [DEPLOYMENT.md](../DEPLOYMENT.md) for detailed deployment instructions.

### Quick Deploy

**Vercel:**
```bash
vercel --prod
```

**Netlify:**
```bash
netlify deploy --prod
```

## Configuration

### API Endpoint

The API base URL is set in `app.js`:

```javascript
const API_BASE_URL = window.__API_BASE_URL__ || 'http://localhost:8000/api/v1';
```

Override by setting `window.__API_BASE_URL__` before loading `app.js`.

### Tailwind Theme

Edit `tailwind.config.js` to customize:
- Colors (brand, EU, SK)
- Fonts
- Breakpoints

## Features

### 1. Chat Interface
- Real-time AI responses
- Source citations with jurisdiction badges
- Confidence scores
- Multi-language support

### 2. Hybrid Search
- Vector semantic search
- Full-text lexical search
- RRF (Reciprocal Rank Fusion)
- Jurisdiction filtering

### 3. Document Management
- Upload PDF, DOCX, TXT
- Automatic chunking & embedding
- Metadata extraction
- Delete documents

## Browser Support

- Chrome/Edge 90+
- Firefox 88+
- Safari 14+
- Mobile browsers (iOS Safari, Chrome Android)

## Performance

- Lighthouse Score: 95+ (all categories)
- First Contentful Paint: < 1s
- Time to Interactive: < 2s
- Total Bundle Size: < 100KB (gzipped)

## SEO

- ✅ Meta tags (title, description, keywords)
- ✅ Open Graph (Facebook, LinkedIn)
- ✅ Twitter Cards
- ✅ Structured data ready
- ✅ Sitemap.xml
- ✅ Robots.txt
- ✅ Semantic HTML

## Accessibility

- WCAG 2.1 Level AA compliant
- Keyboard navigation
- ARIA labels
- Screen reader friendly
- High contrast support

## Contributing

1. Create feature branch
2. Make changes
3. Test locally with `npm run dev`
4. Build with `npm run build`
5. Submit PR

## License

MIT

