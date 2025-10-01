# URL Checker for Bug Bounty Hunters

A high-performance command-line tool designed for bug bounty reconnaissance. Process massive URL lists (100k+), validate endpoints with concurrent requests, and generate interactive HTML reports with advanced filtering capabilities.

## Features

- ✅ Process 100k+ URLs efficiently with concurrent HTTP checking
- 🎯 Filter by status codes (200, 300-399, 403 by default)
- 🔍 Domain filtering with wildcard support (*.example.com)
- 📊 Group URLs by response size to identify similar endpoints
- 🎨 Interactive HTML report with real-time filtering
- 🚀 Optimized for large datasets with persistent filter status indicators
- 📝 Error logging for DNS failures and timeouts

## Installation

Dependencies are automatically installed via UPM:
- aiohttp
- jinja2
- tqdm
- colorama

## Usage

### Basic Usage

```bash
# From file
python urlchecker.py sample_urls.txt

# From stdin
cat urls.txt | python urlchecker.py

# With options
python urlchecker.py urls.txt -o report.html -c 50 -v
```

### Options

- `-o, --output`: Output HTML file (default: url_results.html)
- `-c, --concurrency`: Number of concurrent requests (default: 20)
- `-t, --timeout`: Request timeout in seconds (default: 10)
- `-d, --domain`: Filter by domain with wildcard support (e.g., *.medibuddy.in)
- `-i, --include`: Include additional status codes (e.g., 401,429)
- `-v, --verbose`: Verbose output (print per-URL progress)

### Examples

```bash
# Filter by domain
python urlchecker.py urls.txt -d "*.example.com"

# Include additional status codes
python urlchecker.py urls.txt -i "401,429"

# High concurrency for faster processing
python urlchecker.py urls.txt -c 100

# Verbose mode
python urlchecker.py urls.txt -v
```

## HTML Report Features

The generated HTML report includes:

- **Dashboard**: Summary statistics and filter controls
- **Dual-mode filtering**: Exclude or Include mode
- **Extension filters**: .js, .json, .css, .html, .php, etc.
- **Word filters**: Custom word-based filtering
- **Filter status**: Always visible "X lines hidden" indicator
- **Responsive design**: Works on all devices
- **Copy to clipboard**: Easy URL copying

## Performance

Optimized for large datasets:
- Backend processing handles 100k+ URLs efficiently with batch processing (1000 URLs per batch)
- Concurrent HTTP requests with configurable limits (default: 20)
- HEAD requests first for efficiency, with intelligent fallback to GET on 405/501 errors
- No response body reads unless absolutely necessary - uses Content-Length headers

**HTML Report Scalability:**
- Optimized for typical bug bounty use cases: 1k-20k URLs
- Client-side filtering uses separate counters for fast status updates
- Filter status indicators remain visible and accurate regardless of dataset size
- For datasets approaching 100k URLs, consider that all results are rendered in the HTML (most hidden by default). While functional, browser performance may degrade with extremely large datasets. For true 100k+ scale, consider processing results in batches or implementing virtualization

## Testing

Run with sample URLs:
```bash
python urlchecker.py sample_urls.txt
```

Then open `url_results.html` in your browser to view the interactive report.
