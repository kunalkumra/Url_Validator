#!/usr/bin/env python3

import asyncio
import aiohttp
import argparse
import sys
import json
import time
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from collections import defaultdict
from fnmatch import fnmatch
from tqdm import tqdm
from colorama import init, Fore, Style
from jinja2 import Environment, select_autoescape

init(autoreset=True)

__version__ = "1.0.1"


class URLChecker:
    def __init__(self, args):
        self.args = args
        self.results = defaultdict(lambda: defaultdict(list))
        self.errors = []
        self.stats = {
            'total': 0,
            'valid': 0,
            'errors': 0,
            'start_time': None,
            'end_time': None
        }
        self.seen_urls = set()
        self.default_status_codes = {200} | set(range(300, 400)) | {403}
        
    def match_domain(self, url):
        if not self.args.domain:
            return True
        parsed = urlparse(url)
        domain = parsed.hostname or parsed.netloc
        return fnmatch(domain, self.args.domain)
    
    def get_extension(self, url):
        parsed = urlparse(url)
        path = parsed.path
        if '.' in path:
            parts = path.split('/')[-1].split('.')
            if len(parts) > 1:
                return parts[-1].lower()
        return None
    
    async def check_url(self, session, url, pbar=None):
        try:
            if self.args.verbose:
                print(f"{Fore.CYAN}Checking: {url}")
            
            timeout = aiohttp.ClientTimeout(total=self.args.timeout)
            status = None
            size = None
            
            try:
                async with session.head(url, timeout=timeout, allow_redirects=False) as response:
                    status = response.status
                    
                    if status in [405, 501]:
                        async with session.get(url, timeout=timeout, allow_redirects=False) as get_response:
                            status = get_response.status
                            content_length = get_response.headers.get('Content-Length')
                            size = int(content_length) if content_length else None
                    else:
                        content_length = response.headers.get('Content-Length')
                        size = int(content_length) if content_length else None
            except (aiohttp.ClientResponseError, aiohttp.ClientError):
                async with session.get(url, timeout=timeout, allow_redirects=False) as response:
                    status = response.status
                    content_length = response.headers.get('Content-Length')
                    size = int(content_length) if content_length else None
            
            if pbar:
                pbar.update(1)
            
            return {
                'url': url,
                'status': status,
                'size': size or 0,
                'error': None
            }
        except asyncio.TimeoutError:
            if pbar:
                pbar.update(1)
            return {'url': url, 'status': None, 'size': None, 'error': 'Timeout'}
        except aiohttp.ClientConnectorError as e:
            if pbar:
                pbar.update(1)
            return {'url': url, 'status': None, 'size': None, 'error': f'DNS/Connection: {str(e)[:100]}'}
        except Exception as e:
            if pbar:
                pbar.update(1)
            return {'url': url, 'status': None, 'size': None, 'error': f'Error: {str(e)[:100]}'}
    
    async def process_batch(self, session, urls, pbar, semaphore):
        tasks = []
        for url in urls:
            async def bounded_check(u=url):
                async with semaphore:
                    return await self.check_url(session, u, pbar)
            tasks.append(bounded_check())
        return await asyncio.gather(*tasks)
    
    async def process_urls(self, urls):
        self.stats['start_time'] = time.time()
        
        batch_size = 1000
        connector = aiohttp.TCPConnector(limit=self.args.concurrency)
        timeout = aiohttp.ClientTimeout(total=self.args.timeout)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            semaphore = asyncio.Semaphore(self.args.concurrency)
            
            with tqdm(total=len(urls), desc="Processing URLs", unit="url", disable=not sys.stderr.isatty()) as pbar:
                all_results = []
                for i in range(0, len(urls), batch_size):
                    batch = urls[i:i + batch_size]
                    batch_results = await self.process_batch(session, batch, pbar, semaphore)
                    all_results.extend(batch_results)
                
                results = all_results
        
        included_codes = self.default_status_codes.copy()
        if self.args.include:
            for code in self.args.include.split(','):
                try:
                    included_codes.add(int(code.strip()))
                except ValueError:
                    pass
        
        for result in results:
            self.stats['total'] += 1
            
            if result['error']:
                self.stats['errors'] += 1
                self.errors.append(result)
            elif result['status'] in included_codes:
                self.stats['valid'] += 1
                status = result['status']
                size = result['size']
                self.results[status][size].append(result['url'])
        
        self.stats['end_time'] = time.time()
    
    def generate_html_report(self, output_file):
        template_str = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>URL Checker Report</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            display: flex;
            gap: 20px;
            max-width: 1600px;
            margin: 0 auto;
        }
        
        .sidebar {
            width: 320px;
            background: white;
            border-radius: 12px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            height: fit-content;
            position: sticky;
            top: 20px;
            transition: width 0.3s ease;
        }
        
        .sidebar.collapsed {
            width: 50px;
        }
        
        .sidebar-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 24px;
            cursor: pointer;
            border-bottom: 1px solid #e9ecef;
        }
        
        .sidebar-toggle {
            font-size: 20px;
            transition: transform 0.3s;
        }
        
        .sidebar.collapsed .sidebar-toggle {
            transform: rotate(180deg);
        }
        
        .sidebar-content {
            padding: 24px;
            overflow: hidden;
            transition: opacity 0.3s;
        }
        
        .sidebar.collapsed .sidebar-content {
            opacity: 0;
            height: 0;
            padding: 0;
        }
        
        .sidebar.collapsed h2 {
            display: none;
        }
        
        .stats {
            background: #f8f9fa;
            border-radius: 8px;
            padding: 16px;
            margin-bottom: 24px;
        }
        
        .stat-item {
            display: flex;
            justify-content: space-between;
            margin: 8px 0;
            font-size: 14px;
        }
        
        .stat-label {
            color: #666;
        }
        
        .stat-value {
            font-weight: 600;
            color: #333;
        }
        
        .filter-section {
            margin-top: 24px;
        }
        
        .filter-section h3 {
            font-size: 16px;
            color: #333;
            margin-bottom: 12px;
        }
        
        .filter-mode {
            display: flex;
            gap: 12px;
            margin-bottom: 16px;
        }
        
        .filter-mode label {
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 14px;
            cursor: pointer;
        }
        
        .checkbox-group {
            display: flex;
            flex-direction: column;
            gap: 8px;
            margin-bottom: 16px;
        }
        
        .checkbox-group label {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 14px;
            cursor: pointer;
        }
        
        .custom-filter {
            display: flex;
            gap: 8px;
            margin-bottom: 8px;
        }
        
        .custom-filter input {
            flex: 1;
            padding: 8px 12px;
            border: 1px solid #ddd;
            border-radius: 6px;
            font-size: 14px;
        }
        
        .custom-filter button {
            padding: 8px 16px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
        }
        
        .custom-filter button:hover {
            background: #5568d3;
        }
        
        .custom-items {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 8px;
        }
        
        .custom-item {
            display: flex;
            align-items: center;
            gap: 6px;
            background: #e9ecef;
            padding: 4px 10px;
            border-radius: 16px;
            font-size: 12px;
        }
        
        .custom-item .remove {
            cursor: pointer;
            color: #dc3545;
            font-weight: bold;
        }
        
        .filter-status {
            background: #fff3cd;
            border: 1px solid #ffc107;
            border-radius: 8px;
            padding: 12px;
            margin-bottom: 16px;
            font-size: 14px;
            color: #856404;
            position: sticky;
            top: 0;
            z-index: 100;
        }
        
        .clear-filters {
            width: 100%;
            padding: 10px;
            background: #dc3545;
            color: white;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            margin-top: 8px;
            position: sticky;
            bottom: 0;
        }
        
        .clear-filters:hover {
            background: #c82333;
        }
        
        .reset-filters {
            width: 100%;
            padding: 10px;
            background: #6c757d;
            color: white;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            margin-top: 8px;
        }
        
        .reset-filters:hover {
            background: #5a6268;
        }
        
        .main-content {
            flex: 1;
            min-width: 0;
        }
        
        .header {
            background: white;
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        
        .header h1 {
            color: #333;
            margin-bottom: 8px;
        }
        
        .header p {
            color: #666;
            font-size: 14px;
        }
        
        .status-card {
            background: white;
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        
        .status-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            cursor: pointer;
            margin-bottom: 16px;
        }
        
        .status-title {
            display: flex;
            align-items: center;
            gap: 12px;
        }
        
        .status-badge {
            padding: 6px 16px;
            border-radius: 20px;
            font-weight: 600;
            font-size: 14px;
        }
        
        .status-200 { background: #d4edda; color: #155724; }
        .status-3xx { background: #fff3cd; color: #856404; }
        .status-403 { background: #f8d7da; color: #721c24; }
        .status-other { background: #d1ecf1; color: #0c5460; }
        
        .toggle-icon {
            font-size: 20px;
            transition: transform 0.3s;
        }
        
        .toggle-icon.collapsed {
            transform: rotate(-90deg);
        }
        
        .status-content {
            max-height: 10000px;
            overflow: hidden;
            transition: max-height 0.3s ease;
        }
        
        .status-content.collapsed {
            max-height: 0;
        }
        
        .size-group {
            margin-bottom: 24px;
        }
        
        .size-header {
            background: #f8f9fa;
            padding: 12px 16px;
            border-radius: 8px;
            margin-bottom: 12px;
            font-weight: 600;
            color: #495057;
        }
        
        .url-table {
            width: 100%;
            border-collapse: collapse;
        }
        
        .url-table thead {
            background: #f8f9fa;
        }
        
        .url-table th {
            padding: 12px;
            text-align: left;
            font-weight: 600;
            color: #495057;
            font-size: 14px;
        }
        
        .url-table td {
            padding: 12px;
            border-top: 1px solid #dee2e6;
            font-size: 14px;
        }
        
        .url-table tr:hover {
            background: #f8f9fa;
        }
        
        .url-link {
            color: #667eea;
            text-decoration: none;
            word-break: break-all;
        }
        
        .url-link:hover {
            text-decoration: underline;
        }
        
        .copy-btn {
            background: none;
            border: none;
            cursor: pointer;
            font-size: 18px;
            padding: 4px;
            transition: transform 0.2s;
        }
        
        .copy-btn:hover {
            transform: scale(1.2);
        }
        
        .copy-btn.success {
            color: #28a745;
        }
        
        .show-more-btn {
            width: 100%;
            padding: 10px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            margin-top: 12px;
        }
        
        .show-more-btn:hover {
            background: #5568d3;
        }
        
        .error-section {
            background: white;
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        
        .error-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            cursor: pointer;
        }
        
        .error-content {
            max-height: 10000px;
            overflow: hidden;
            transition: max-height 0.3s ease;
            margin-top: 16px;
        }
        
        .error-content.collapsed {
            max-height: 0;
            margin-top: 0;
        }
        
        .error-item {
            padding: 12px;
            background: #f8f9fa;
            border-left: 4px solid #dc3545;
            margin-bottom: 8px;
            border-radius: 4px;
            font-size: 14px;
        }
        
        .url-row.hidden {
            display: none;
        }
        
        @media (max-width: 1024px) {
            .container {
                flex-direction: column;
            }
            .sidebar {
                width: 100%;
                position: static;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="sidebar" id="sidebar">
            <div class="sidebar-header" onclick="toggleSidebar()">
                <h2>Dashboard</h2>
                <span class="sidebar-toggle">◀</span>
            </div>
            
            <div class="sidebar-content">
                <div class="stats">
                    <div class="stat-item">
                        <span class="stat-label">Total URLs:</span>
                        <span class="stat-value">{{ stats.total }}</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">Valid Responses:</span>
                        <span class="stat-value">{{ stats.valid }}</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">Errors:</span>
                        <span class="stat-value">{{ stats.errors }}</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">Time Taken:</span>
                        <span class="stat-value">{{ "%.2f"|format(stats.time_taken) }}s</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">Last Checked:</span>
                        <span class="stat-value">{{ stats.timestamp }}</span>
                    </div>
                </div>
                
                <div class="filter-section">
                    <h3>Filters</h3>
                    
                    <div class="filter-mode">
                        <label>
                            <input type="radio" name="filterMode" value="exclude" checked>
                            Exclude
                        </label>
                        <label>
                            <input type="radio" name="filterMode" value="include">
                            Include
                        </label>
                    </div>
                    
                    <h4 style="font-size: 14px; margin-bottom: 8px; color: #666;">Extensions</h4>
                    <div class="checkbox-group" id="extensionCheckboxes">
                        <label><input type="checkbox" value="js"> .js</label>
                        <label><input type="checkbox" value="json"> .json</label>
                        <label><input type="checkbox" value="css"> .css</label>
                        <label><input type="checkbox" value="html"> .html</label>
                        <label><input type="checkbox" value="java"> .java</label>
                        <label><input type="checkbox" value="php"> .php</label>
                        <label><input type="checkbox" value="txt"> .txt</label>
                        <label><input type="checkbox" value="xml"> .xml</label>
                        <label><input type="checkbox" value="pdf"> .pdf</label>
                    </div>
                    
                    <div class="custom-filter">
                        <input type="text" id="customExtInput" placeholder="Add custom extension">
                        <button onclick="addCustomExtension()">Add</button>
                    </div>
                    <div class="custom-items" id="customExtensions"></div>
                    
                    <h4 style="font-size: 14px; margin: 16px 0 8px; color: #666;">Words</h4>
                    <div class="custom-filter">
                        <input type="text" id="customWordInput" placeholder="Add custom word">
                        <button onclick="addCustomWord()">Add</button>
                    </div>
                    <div class="custom-items" id="customWords"></div>
                    
                    <div id="filterStatus" class="filter-status" style="display: none;"></div>
                    <button id="clearFiltersBtn" class="clear-filters" style="display: none;" onclick="clearAllFilters()">Clear All Filters</button>
                    <button class="reset-filters" onclick="resetFilters()">Reset Filters</button>
                </div>
            </div>
        </div>
        
        <div class="main-content">
            <div class="header">
                <h1>URL Checker Report</h1>
                <p>Bug Bounty Reconnaissance Tool</p>
            </div>
            
            {% if errors %}
            <div class="error-section">
                <div class="error-header" onclick="toggleErrors()">
                    <h2 style="color: #dc3545;">Errors ({{ errors|length }})</h2>
                    <span class="toggle-icon" id="errorToggle">▼</span>
                </div>
                <div class="error-content collapsed" id="errorContent">
                    {% for error in errors %}
                    <div class="error-item">
                        <strong>{{ error.url|e }}</strong><br>
                        {{ error.error|e }}
                    </div>
                    {% endfor %}
                </div>
            </div>
            {% endif %}
            
            {% for status_code in sorted_statuses %}
            <div class="status-card">
                <div class="status-header" onclick="toggleStatus({{ status_code }})">
                    <div class="status-title">
                        <span class="status-badge {% if status_code == 200 %}status-200{% elif 300 <= status_code < 400 %}status-3xx{% elif status_code == 403 %}status-403{% else %}status-other{% endif %}">
                            {{ status_code }}
                        </span>
                        <h2>{{ status_names.get(status_code, 'Unknown') }}</h2>
                    </div>
                    <span class="toggle-icon" id="toggle-{{ status_code }}">▼</span>
                </div>
                <div class="status-content" id="content-{{ status_code }}">
                    {% for size, urls in results[status_code].items() %}
                    <div class="size-group">
                        <div class="size-header">Response Size: {{ size }} bytes ({{ urls|length }} URLs)</div>
                        <table class="url-table">
                            <thead>
                                <tr>
                                    <th style="width: 70%;">URL</th>
                                    <th style="width: 20%;">Size</th>
                                    <th style="width: 10%;">Action</th>
                                </tr>
                            </thead>
                            <tbody>
                                {% for url in urls[:4] %}
                                <tr class="url-row" data-url="{{ url|e }}" data-ext="{{ (url.split('.')[-1].split('?')[0].split('#')[0].lower() if '.' in url.split('/')[-1] else '')|e }}">
                                    <td><a href="{{ url|e }}" target="_blank" class="url-link">{{ url|e }}</a></td>
                                    <td>{{ size }}</td>
                                    <td><button class="copy-btn" onclick="copyUrl(this, {{ url|tojson }})">📋</button></td>
                                </tr>
                                {% endfor %}
                                {% if urls|length > 4 %}
                                {% for url in urls[4:] %}
                                <tr class="url-row hidden" data-url="{{ url|e }}" data-ext="{{ (url.split('.')[-1].split('?')[0].split('#')[0].lower() if '.' in url.split('/')[-1] else '')|e }}" data-more-group="{{ status_code }}-{{ size }}">
                                    <td><a href="{{ url|e }}" target="_blank" class="url-link">{{ url|e }}</a></td>
                                    <td>{{ size }}</td>
                                    <td><button class="copy-btn" onclick="copyUrl(this, {{ url|tojson }})">📋</button></td>
                                </tr>
                                {% endfor %}
                                <tr data-more-group="{{ status_code }}-{{ size }}">
                                    <td colspan="3">
                                        <button class="show-more-btn" onclick="showMore('{{ status_code }}-{{ size }}')">
                                            Show {{ urls|length - 4 }} more URLs
                                        </button>
                                    </td>
                                </tr>
                                {% endif %}
                            </tbody>
                        </table>
                    </div>
                    {% endfor %}
                </div>
            </div>
            {% endfor %}
        </div>
    </div>
    
    <script>
        const customExtensions = new Set();
        const customWords = new Set();
        let totalUrls = 0;
        let visibleUrls = 0;
        
        function toggleSidebar() {
            document.getElementById('sidebar').classList.toggle('collapsed');
        }
        
        function toggleStatus(statusCode) {
            const content = document.getElementById(`content-${statusCode}`);
            const toggle = document.getElementById(`toggle-${statusCode}`);
            content.classList.toggle('collapsed');
            toggle.classList.toggle('collapsed');
        }
        
        function toggleErrors() {
            const content = document.getElementById('errorContent');
            const toggle = document.getElementById('errorToggle');
            content.classList.toggle('collapsed');
            toggle.classList.toggle('collapsed');
        }
        
        function copyUrl(btn, url) {
            navigator.clipboard.writeText(url);
            btn.classList.add('success');
            setTimeout(() => btn.classList.remove('success'), 1000);
        }
        
        function showMore(group) {
            const rows = document.querySelectorAll(`[data-more-group="${group}"]`);
            rows.forEach(row => {
                row.classList.remove('hidden');
                if (row.querySelector('.url-row, .url-link')) {
                    applyFilterToRow(row);
                }
            });
        }
        
        function addCustomExtension() {
            const input = document.getElementById('customExtInput');
            const value = input.value.trim().toLowerCase().replace(/^\./, '');
            if (value && !customExtensions.has(value)) {
                customExtensions.add(value);
                updateCustomExtensions();
                input.value = '';
                applyFilters();
            }
        }
        
        function addCustomWord() {
            const input = document.getElementById('customWordInput');
            const value = input.value.trim();
            if (value && !customWords.has(value)) {
                customWords.add(value);
                updateCustomWords();
                input.value = '';
                applyFilters();
            }
        }
        
        function updateCustomExtensions() {
            const container = document.getElementById('customExtensions');
            container.innerHTML = '';
            customExtensions.forEach(ext => {
                const item = document.createElement('div');
                item.className = 'custom-item';
                item.innerHTML = `<span>.${ext}</span><span class="remove" onclick="removeCustomExtension('${ext}')">✗</span>`;
                container.appendChild(item);
            });
        }
        
        function updateCustomWords() {
            const container = document.getElementById('customWords');
            container.innerHTML = '';
            customWords.forEach(word => {
                const item = document.createElement('div');
                item.className = 'custom-item';
                const escapedWord = word.replace(/'/g, "\\'");
                item.innerHTML = `<span>${word}</span><span class="remove" onclick="removeCustomWord('${escapedWord}')">✗</span>`;
                container.appendChild(item);
            });
        }
        
        function removeCustomExtension(ext) {
            customExtensions.delete(ext);
            updateCustomExtensions();
            applyFilters();
        }
        
        function removeCustomWord(word) {
            customWords.delete(word);
            updateCustomWords();
            applyFilters();
        }
        
        function applyFilterToRow(row) {
            const mode = document.querySelector('input[name="filterMode"]:checked').value;
            const checkboxes = document.querySelectorAll('#extensionCheckboxes input[type="checkbox"]:checked');
            const selectedExts = new Set([...Array.from(checkboxes).map(cb => cb.value), ...customExtensions]);
            
            const url = row.dataset.url.toLowerCase();
            const ext = row.dataset.ext;
            
            let matchesExt = selectedExts.size === 0 ? false : selectedExts.has(ext);
            let matchesWord = false;
            
            if (customWords.size > 0) {
                customWords.forEach(word => {
                    if (url.includes(word.toLowerCase())) {
                        matchesWord = true;
                    }
                });
            }
            
            const matches = matchesExt || matchesWord;
            
            if (mode === 'exclude') {
                if (matches) {
                    row.style.display = 'none';
                    return false;
                } else {
                    row.style.display = '';
                    return true;
                }
            } else {
                if (selectedExts.size === 0 && customWords.size === 0) {
                    row.style.display = '';
                    return true;
                } else if (matches) {
                    row.style.display = '';
                    return true;
                } else {
                    row.style.display = 'none';
                    return false;
                }
            }
        }
        
        function applyFilters() {
            const allRows = document.querySelectorAll('.url-row');
            totalUrls = allRows.length;
            visibleUrls = 0;
            
            allRows.forEach(row => {
                if (applyFilterToRow(row)) {
                    visibleUrls++;
                }
            });
            
            updateFilterStatus();
        }
        
        function updateFilterStatus() {
            const statusDiv = document.getElementById('filterStatus');
            const clearBtn = document.getElementById('clearFiltersBtn');
            const mode = document.querySelector('input[name="filterMode"]:checked').value;
            const hiddenCount = totalUrls - visibleUrls;
            const hasFilters = hiddenCount > 0 || visibleUrls < totalUrls;
            
            if (hasFilters) {
                statusDiv.textContent = mode === 'exclude' ? 
                    `${hiddenCount} URLs hidden, ${visibleUrls} shown` :
                    `${visibleUrls} URLs shown, ${hiddenCount} hidden`;
                statusDiv.style.display = 'block';
                clearBtn.style.display = 'block';
            } else {
                statusDiv.style.display = 'none';
                clearBtn.style.display = 'none';
            }
        }
        
        function clearAllFilters() {
            document.querySelectorAll('#extensionCheckboxes input[type="checkbox"]').forEach(cb => cb.checked = false);
            customExtensions.clear();
            customWords.clear();
            updateCustomExtensions();
            updateCustomWords();
            applyFilters();
        }
        
        function resetFilters() {
            document.querySelector('input[name="filterMode"][value="exclude"]').checked = true;
            clearAllFilters();
        }
        
        totalUrls = document.querySelectorAll('.url-row').length;
        visibleUrls = totalUrls;
        
        document.querySelectorAll('#extensionCheckboxes input[type="checkbox"]').forEach(cb => {
            cb.addEventListener('change', applyFilters);
        });
        
        document.querySelectorAll('input[name="filterMode"]').forEach(radio => {
            radio.addEventListener('change', applyFilters);
        });
        
        document.getElementById('customExtInput').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') addCustomExtension();
        });
        
        document.getElementById('customWordInput').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') addCustomWord();
        });
    </script>
</body>
</html>'''
        
        status_names = {
            200: "OK",
            301: "Moved Permanently",
            302: "Found",
            303: "See Other",
            304: "Not Modified",
            307: "Temporary Redirect",
            308: "Permanent Redirect",
            403: "Forbidden"
        }
        
        sorted_statuses = sorted(self.results.keys(), key=lambda x: (0 if x == 200 else 1 if 300 <= x < 400 else 2 if x == 403 else 3, x))
        
        env = Environment(autoescape=select_autoescape(['html']))
        template = env.from_string(template_str)
        html_content = template.render(
            results=self.results,
            errors=self.errors,
            stats={
                'total': self.stats['total'],
                'valid': self.stats['valid'],
                'errors': self.stats['errors'],
                'time_taken': self.stats['end_time'] - self.stats['start_time'],
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            },
            sorted_statuses=sorted_statuses,
            status_names=status_names
        )
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"\n{Fore.GREEN}✓ HTML report generated: {output_file}")
        print(f"{Fore.CYAN}Open it in your browser to view the results.")


def read_urls_from_input(args):
    urls = []
    
    if args.file:
        try:
            with open(args.file, 'r') as f:
                urls = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            print(f"{Fore.RED}Error: File '{args.file}' not found")
            sys.exit(1)
    elif not sys.stdin.isatty():
        urls = [line.strip() for line in sys.stdin if line.strip()]
    else:
        print(f"{Fore.RED}Error: Please provide URLs via file or stdin")
        sys.exit(1)
    
    return urls


def main():
    parser = argparse.ArgumentParser(
        description="URL Checker for Bug Bounty Hunters",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('file', nargs='?', help='File containing URLs (one per line)')
    parser.add_argument('-o', '--output', default='url_results.html', help='Output HTML file (default: url_results.html)')
    parser.add_argument('-c', '--concurrency', type=int, default=20, help='Number of concurrent requests (default: 20)')
    parser.add_argument('-t', '--timeout', type=int, default=10, help='Request timeout in seconds (default: 10)')
    parser.add_argument('-d', '--domain', help='Filter by domain with wildcard support (e.g., *.example.com)')
    parser.add_argument('-i', '--include', help='Include additional status codes (comma-separated, e.g., 401,429)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output (print per-URL progress)')
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    
    args = parser.parse_args()
    
    print(f"{Fore.CYAN}URL Checker for Bug Bounty v{__version__}")
    print(f"{Fore.CYAN}{'='*50}\n")
    
    urls = read_urls_from_input(args)
    
    print(f"{Fore.YELLOW}Loaded {len(urls)} URLs")
    
    seen = set()
    unique_urls = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            unique_urls.append(url)
    
    print(f"{Fore.YELLOW}Deduplicated to {len(unique_urls)} unique URLs")
    
    if args.domain:
        checker = URLChecker(args)
        filtered_urls = [url for url in unique_urls if checker.match_domain(url)]
        print(f"{Fore.YELLOW}Filtered to {len(filtered_urls)} URLs matching domain '{args.domain}'")
        unique_urls = filtered_urls
    
    if not unique_urls:
        print(f"{Fore.RED}No URLs to process")
        sys.exit(1)
    
    checker = URLChecker(args)
    
    asyncio.run(checker.process_urls(unique_urls))
    
    print(f"\n{Fore.GREEN}Processing complete!")
    print(f"{Fore.CYAN}Total: {checker.stats['total']}, Valid: {checker.stats['valid']}, Errors: {checker.stats['errors']}")
    
    checker.generate_html_report(args.output)


if __name__ == "__main__":
    main()
