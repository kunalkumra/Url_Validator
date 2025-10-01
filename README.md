
# URL Checker for Bug Bounty Hunters

🎯 **Process massive URL lists from reconnaissance tools like waybackurls, gau, urlfinder, VirusTotal, etc. Get interactive HTML reports with smart filtering to find interesting endpoints efficiently.**

## What is this tool?

A high-performance Python CLI tool designed specifically for bug bounty reconnaissance workflows. It takes the massive URL lists you collect from various discovery tools and helps you analyze them systematically to find valuable endpoints.

**Perfect for processing URLs from:**
- `waybackurls` - Historical URLs from Wayback Machine
- `gau` - URLs from multiple sources (Wayback, Common Crawl, etc.)  
- `urlfinder` - URLs from various APIs
- VirusTotal URL dumps
- Any tool that outputs URL lists

## Why use this tool?

- **Handle massive scale**: Process 100k+ URLs efficiently with concurrent HTTP checking
- **Smart filtering**: Group similar endpoints by response size to identify patterns
- **Interactive analysis**: Real-time filtering in HTML reports without re-running scans
- **Bug bounty focused**: Filters for security-relevant status codes (200, 3xx, 403) by default
- **Post-discovery workflow**: Designed for analyzing URLs after initial discovery, not basic probing

*Note: While httpx is great for basic HTTP probing during discovery, this tool excels at post-discovery analysis with interactive filtering and endpoint grouping.*

## When to use this tool?

**Use this tool when you:**
- Have large URL lists from reconnaissance and need to find interesting endpoints
- Want to group similar responses to identify patterns
- Need interactive filtering to focus on specific file types or endpoints
- Are doing post-discovery analysis rather than initial URL validation

**Typical workflow:**
```bash
# 1. Collect URLs from multiple sources
waybackurls target.com > urls.txt
gau target.com >> urls.txt
echo "target.com" | subfinder | httpx | urlfinder >> urls.txt

# 2. Process and analyze with URL Checker
python urlchecker.py urls.txt -d "*.target.com" -o analysis.html

# 3. Open analysis.html to filter and find interesting endpoints
```

## Installation

No manual installation needed in Replit! Dependencies are automatically managed:
- `aiohttp` - Async HTTP requests
- `jinja2` - HTML report generation  
- `tqdm` - Progress bars
- `colorama` - Colored output

## Usage

### Basic Usage

```bash
# From file
python urlchecker.py urls.txt

# From stdin (pipe from other tools)
cat urls.txt | python urlchecker.py
waybackurls target.com | python urlchecker.py

# With custom output file
python urlchecker.py urls.txt -o my_report.html
```

### Command Line Options

```bash
python urlchecker.py [file] [options]

Options:
  -o, --output FILE     Output HTML file (default: url_results.html)
  -c, --concurrency N   Concurrent requests (default: 20, max recommended: 100)
  -t, --timeout N       Request timeout in seconds (default: 10)
  -d, --domain PATTERN  Filter by domain with wildcards (e.g., *.example.com)
  -i, --include CODES   Include additional status codes (e.g., 401,429)
  -v, --verbose         Show detailed progress per URL
```

### Examples

```bash
# Filter for specific domain and subdomains
python urlchecker.py urls.txt -d "*.hackerone.com"

# Include additional status codes (401 Unauthorized, 429 Rate Limited)
python urlchecker.py urls.txt -i "401,429"

# High-speed processing with more concurrent requests
python urlchecker.py urls.txt -c 50

# Verbose mode to see each URL being processed
python urlchecker.py urls.txt -v

# Process waybackurls output directly
waybackurls target.com | python urlchecker.py -o wayback_analysis.html
```

## HTML Report Features

The generated interactive report includes:

### Dashboard Controls
- **Statistics**: Total URLs, valid responses, errors, processing time
- **Filter modes**: Exclude unwanted content OR include only specific content
- **Status indicator**: Always visible "X URLs hidden/shown" counter

### Smart Filtering
- **Extensions**: `.js`, `.json`, `.css`, `.html`, `.php`, etc. + custom extensions
- **Words**: Filter URLs containing specific words (case-insensitive)
- **Real-time**: Instant filtering without page reload
- **Persistent**: Filter status always visible regardless of dataset size

### Response Analysis
- **Grouped by status code**: 200 (OK), 3xx (Redirects), 403 (Forbidden), etc.
- **Grouped by response size**: Identify similar endpoints with same response lengths
- **Collapsible sections**: Organize large datasets efficiently
- **Copy to clipboard**: One-click URL copying for further testing

## Performance

**Backend Processing:**
- Handles 100k+ URLs with efficient batch processing (1000 URLs per batch)
- Configurable concurrent HTTP requests (default: 20, recommended max: 100)
- Smart HTTP method handling (HEAD first, fallback to GET when needed)
- Memory-efficient: Uses Content-Length headers instead of downloading response bodies

**HTML Report:**
- Optimized for typical bug bounty datasets (1k-20k URLs)
- Client-side filtering with real-time status updates
- Responsive design works on all devices
- No backend required - fully self-contained HTML file

## Quick Start

1. **Run the demo:**
   ```bash
   python urlchecker.py sample_urls.txt
   ```

2. **Open `url_results.html` in your browser**

3. **Try the filters:**
   - Check/uncheck file extensions
   - Add custom words to filter
   - Switch between Exclude/Include modes
   - Watch the status counter update in real-time

4. **Process your own URLs:**
   ```bash
   python urlchecker.py your_urls.txt -d "*.yourtarget.com" -o your_report.html
   ```

## Tips for Bug Bounty

- **Start with domain filtering** (`-d "*.target.com"`) to focus on your target
- **Look for interesting extensions** like `.json`, `.config`, `.backup` in the HTML report
- **Group by response size** to find similar endpoints (same error pages, API responses)
- **Use include mode** to focus on specific file types you want to analyze
- **Process large datasets in batches** if you have 100k+ URLs for better browser performance

---

**Ready to analyze your reconnaissance data? Upload your URL list and run the tool!**
