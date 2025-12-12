import json
import os
import re
from statistics import mean
from datetime import datetime
import fitz 

PDF_AVAILABLE = True

# --- Data files ---
COURSES_FILE = 'data/courses.json'
ROUNDS_FILE = 'data/rounds.json'
CLUBS_FILE = 'data/clubs.json'
RULEBOOK_PDF = 'data/2023_Rules_of_Golf.pdf'  # Changed from JSON to PDF
BOOKMARKS_FILE = 'data/bookmarks.json'
RULE_NOTES_FILE = 'data/rule_notes.json'
RULEBOOK_CACHE_FILE = 'data/rulebook_cache.json'  # Cache for parsed structure
PDF_ANNOTATIONS_FILE = 'data/pdf_annotations.json'  # Highlights and notes on PDF pages
PAGE_BOOKMARKS_FILE = 'data/page_bookmarks.json'  # Bookmarked page numbers
STATS_CACHE_FILE = 'data/stats_cache.json'  # Cached computed statistics
USER_PREFS_FILE = 'data/user_prefs.json'  # User preferences (entry mode, etc.)

# Club categories for analytics
CLUB_CATEGORIES = {
    "Driver": {"category": "driver", "loft": 10.5, "order": 1},
    "3 Wood": {"category": "wood", "loft": 15, "order": 2},
    "5 Wood": {"category": "wood", "loft": 18, "order": 3},
    "7 Wood": {"category": "wood", "loft": 21, "order": 4},
    "Hybrid": {"category": "hybrid", "loft": 22, "order": 5},
    "2 Hybrid": {"category": "hybrid", "loft": 18, "order": 5},
    "3 Hybrid": {"category": "hybrid", "loft": 20, "order": 6},
    "4 Hybrid": {"category": "hybrid", "loft": 23, "order": 7},
    "5 Hybrid": {"category": "hybrid", "loft": 26, "order": 8},
    "2 Iron": {"category": "iron", "loft": 18, "order": 9},
    "3 Iron": {"category": "iron", "loft": 21, "order": 10},
    "4 Iron": {"category": "iron", "loft": 24, "order": 11},
    "5 Iron": {"category": "iron", "loft": 27, "order": 12},
    "6 Iron": {"category": "iron", "loft": 30, "order": 13},
    "7 Iron": {"category": "iron", "loft": 34, "order": 14},
    "8 Iron": {"category": "iron", "loft": 38, "order": 15},
    "9 Iron": {"category": "iron", "loft": 42, "order": 16},
    "PW": {"category": "wedge", "loft": 46, "order": 17},
    "GW": {"category": "wedge", "loft": 50, "order": 18},
    "SW": {"category": "wedge", "loft": 54, "order": 19},
    "LW": {"category": "wedge", "loft": 58, "order": 20},
    "Putter": {"category": "putter", "loft": 3, "order": 21},
}


def load_json(filename):
    if not os.path.exists(filename):
        return []
    with open(filename, 'r') as f:
        return json.load(f)


def save_json(filename, data):
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)


class PDFRulebook:
    """
    Direct PDF-based rulebook access.
    Parses the Rules of Golf PDF on-the-fly for searches and browsing.
    """
    
    def __init__(self, pdf_path):
        self.pdf_path = pdf_path
        self.doc = None
        self._cache = None
        self._page_text_cache = {}
        
        if PDF_AVAILABLE and os.path.exists(pdf_path):
            self.doc = fitz.open(pdf_path)
        
    def is_available(self):
        """Check if PDF is loaded and ready."""
        return self.doc is not None
    
    def get_version(self):
        """Return version info from the PDF."""
        if not self.is_available():
            return {"version": "Unknown", "last_updated": "Unknown"}
        
        # Extract version from PDF metadata or first page
        metadata = self.doc.metadata
        title = metadata.get('title', '')
        
        # Try to find year in title or filename
        year_match = re.search(r'20\d{2}', title) or re.search(r'20\d{2}', self.pdf_path)
        version = year_match.group(0) if year_match else "2023"
        
        return {
            "version": version,
            "last_updated": datetime.fromtimestamp(os.path.getmtime(self.pdf_path)).strftime("%Y-%m-%d")
        }
    
    def get_page_text(self, page_num):
        """Get text from a specific page with caching."""
        if page_num in self._page_text_cache:
            return self._page_text_cache[page_num]
        
        if not self.is_available() or page_num >= len(self.doc):
            return ""
        
        text = self.doc[page_num].get_text()
        self._page_text_cache[page_num] = text
        return text
    
    def get_total_pages(self):
        """Return total number of pages."""
        return len(self.doc) if self.is_available() else 0
    
    def _parse_toc_from_pdf(self):
        """
        Parse the Table of Contents directly from the PDF pages 5-9.
        Returns list of {'level': int, 'title': str, 'page': int} dicts.
        """
        if not self.is_available():
            return []
        
        # Extract text from TOC pages (pages 5-9, 0-indexed: 4-8)
        toc_text = ""
        for page_num in range(4, 9):
            if page_num < len(self.doc):
                page = self.doc[page_num]
                toc_text += page.get_text() + "\n"
        
        entries = []
        lines = toc_text.split('\n')
        i = 0
        
        while i < len(lines):
            line = lines[i].strip()
            
            # Skip empty lines, "Contents" header, and standalone page numbers
            if not line or line == "Contents" or (line.isdigit() and len(line) <= 2):
                i += 1
                continue
            
            # Check if line contains backspace character (\b) followed by page number
            # This is how the PDF encodes TOC entries
            if '\b' in line:
                parts = line.split('\b')
                title = parts[0].strip()
                page_str = parts[-1].strip() if len(parts) > 1 else ""
                
                # Page number might be on next line
                if not page_str.isdigit() and i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if next_line.isdigit():
                        page_str = next_line
                        i += 1
                
                if title and page_str.isdigit():
                    page_num = int(page_str)
                    
                    # Determine hierarchy level based on pattern
                    level = 3  # Default: sub-rule (e.g., "1.1", "1.2")
                    
                    # Level 1: Parts (Roman numerals) and top-level items
                    if re.match(r'^[IVX]+\.\s', title):
                        level = 1
                    elif title.startswith('Foreword') or title.startswith('Principal Changes') or \
                         title.startswith('How to Use') or title == 'Index' or \
                         title == 'Other Publications' or 'Definitions' in title:
                        level = 1
                    # Level 2: Rules
                    elif re.match(r'^Rule\s+\d+', title):
                        level = 2
                    
                    # Clean up title (normalize whitespace)
                    title = re.sub(r'\s+', ' ', title).strip()
                    
                    entries.append({
                        'level': level,
                        'title': title,
                        'page': page_num + 1  # Convert to 0-indexed for internal use
                    })
            
            i += 1
        
        return entries
    
    def _parse_structure(self):
        """Parse PDF to extract rule structure. Results are cached."""
        if self._cache is not None:
            return self._cache
        
        # Try to load from cache file first
        if os.path.exists(RULEBOOK_CACHE_FILE):
            try:
                with open(RULEBOOK_CACHE_FILE, 'r') as f:
                    cached = json.load(f)
                    if cached.get('pdf_mtime') == os.path.getmtime(self.pdf_path):
                        self._cache = cached
                        return self._cache
            except (json.JSONDecodeError, OSError):
                pass
        
        if not self.is_available():
            return {"toc": [], "sections": [], "rules": {}}
        
        # Parse TOC directly from PDF
        toc_entries = self._parse_toc_from_pdf()
        
        # Build TOC items with unique IDs
        toc_items = []
        sections = []
        
        for i, entry in enumerate(toc_entries):
            toc_item = {
                "id": f"toc_{i}",
                "level": entry['level'],
                "title": entry['title'],
                "page": entry['page']
            }
            toc_items.append(toc_item)
            
            # Also add to sections for backward compatibility
            if entry['level'] <= 2:
                sections.append({
                    "id": toc_item["id"],
                    "title": entry['title'],
                    "page": entry['page'],
                    "level": entry['level']
                })
        
        self._cache = {
            "toc": toc_items,
            "sections": sections,
            "rules": {},
            "pdf_mtime": os.path.getmtime(self.pdf_path)
        }
        
        # Save cache
        try:
            os.makedirs(os.path.dirname(RULEBOOK_CACHE_FILE), exist_ok=True)
            with open(RULEBOOK_CACHE_FILE, 'w') as f:
                json.dump(self._cache, f)
        except OSError:
            pass
        
        return self._cache
    
    def get_toc(self):
        """Return the full hierarchical table of contents parsed from the PDF."""
        structure = self._parse_structure()
        return structure.get("toc", [])
    
    def get_all_sections(self):
        """Return list of (section_id, section_title) tuples for backward compatibility."""
        structure = self._parse_structure()
        return [(s["id"], s["title"]) for s in structure.get("sections", [])]
    
    def get_all_sections_with_pages(self):
        """Return list of (section_id, section_title, page_num) tuples."""
        structure = self._parse_structure()
        return [(s["id"], s["title"], s.get("page", 0)) for s in structure.get("sections", [])]
    
    def get_section_rules(self, section_id):
        """Get all rules in a specific section."""
        structure = self._parse_structure()
        rules = []
        
        for rule_id, rule in structure["rules"].items():
            if rule.get("section_id") == section_id:
                rules.append({
                    "id": rule["id"],
                    "title": rule["title"],
                    "content": rule.get("content", ""),
                    "page": rule.get("page", 0)
                })
        
        # Sort by rule ID (1.1, 1.2, 1.3, etc.)
        rules.sort(key=lambda x: [int(n) if n.isdigit() else n for n in re.split(r'(\d+)', x["id"])])
        return rules
    
    def get_rule_by_id(self, rule_id):
        """Get a specific rule by its ID."""
        structure = self._parse_structure()
        rule = structure["rules"].get(rule_id)
        
        if not rule:
            return None
        
        # Find section info
        section_id = rule.get("section_id", rule_id.split('.')[0])
        section_title = ""
        for sec in structure["sections"]:
            if sec["id"] == section_id:
                section_title = sec["title"]
                break
        
        return {
            "section_id": section_id,
            "section_title": section_title,
            "rule": {
                "id": rule["id"],
                "title": rule["title"],
                "content": rule.get("content", ""),
                "page": rule.get("page", 0)
            }
        }
    
    def search(self, query, max_results=50):
        """
        Search the PDF for rules matching the query.
        Returns list of matching rules with context.
        """
        if not self.is_available():
            return []
        
        query_lower = query.lower()
        results = []
        structure = self._parse_structure()
        
        # Search in parsed rules first (faster, structured)
        for rule_id, rule in structure["rules"].items():
            score = 0
            
            # Check title match (higher weight)
            if query_lower in rule["title"].lower():
                score += 10
            
            # Check ID match
            if query_lower in rule_id.lower():
                score += 5
            
            # Check content match
            content = rule.get("content", "").lower()
            if query_lower in content:
                score += 1
                # Boost for multiple occurrences
                score += min(content.count(query_lower), 5)
            
            if score > 0:
                # Find section info
                section_id = rule.get("section_id", rule_id.split('.')[0])
                section_title = ""
                for sec in structure["sections"]:
                    if sec["id"] == section_id:
                        section_title = sec["title"]
                        break
                
                results.append({
                    "section_id": section_id,
                    "section_title": section_title,
                    "rule_id": rule["id"],
                    "rule_title": rule["title"],
                    "content": rule.get("content", ""),
                    "page": rule.get("page", 0),
                    "_score": score
                })
        
        # Sort by relevance score
        results.sort(key=lambda x: x["_score"], reverse=True)
        
        # Remove score from results
        for r in results:
            del r["_score"]
        
        return results[:max_results]
    
    def search_pdf_pages(self, query, context_chars=200):
        """
        Direct PDF text search with page references.
        Returns list of (page_num, snippet) tuples.
        """
        if not self.is_available():
            return []
        
        query_lower = query.lower()
        results = []
        
        for page_num in range(len(self.doc)):
            page_text = self.get_page_text(page_num)
            text_lower = page_text.lower()
            
            # Find all occurrences
            start = 0
            while True:
                pos = text_lower.find(query_lower, start)
                if pos == -1:
                    break
                
                # Extract context around match
                ctx_start = max(0, pos - context_chars)
                ctx_end = min(len(page_text), pos + len(query) + context_chars)
                snippet = page_text[ctx_start:ctx_end].strip()
                
                # Clean up snippet
                snippet = ' '.join(snippet.split())
                if ctx_start > 0:
                    snippet = "..." + snippet
                if ctx_end < len(page_text):
                    snippet = snippet + "..."
                
                results.append({
                    "page": page_num + 1,  # 1-indexed for display
                    "snippet": snippet
                })
                
                start = pos + 1
                
                # Limit results per page
                if len([r for r in results if r["page"] == page_num + 1]) >= 3:
                    break
        
        return results
    
    def get_page_content(self, page_num):
        """Get full content of a specific page."""
        if not self.is_available() or page_num < 0 or page_num >= len(self.doc):
            return ""
        return self.get_page_text(page_num)
    
    def clear_cache(self):
        """Clear all caches to force re-parsing."""
        self._cache = None
        self._page_text_cache = {}
        if os.path.exists(RULEBOOK_CACHE_FILE):
            os.remove(RULEBOOK_CACHE_FILE)
    
    def close(self):
        """Close the PDF document."""
        if self.doc:
            self.doc.close()
            self.doc = None


# --- Backend Logic ---
class GolfBackend:
    def __init__(self):
        os.makedirs('data', exist_ok=True)
        self.courses = load_json(COURSES_FILE)
        self.rounds = load_json(ROUNDS_FILE)
        self.clubs = load_json(CLUBS_FILE)
        self.rulebook = self._load_rulebook()
        self.bookmarks = load_json(BOOKMARKS_FILE) if os.path.exists(BOOKMARKS_FILE) else []
        self.rule_notes = load_json(RULE_NOTES_FILE) if os.path.exists(RULE_NOTES_FILE) else {}
        self.pdf_annotations = self._load_pdf_annotations()
        self.page_bookmarks = self._load_page_bookmarks()
        self.user_prefs = self._load_user_prefs()
        self.stats_cache = self._load_stats_cache()
    
    def _load_user_prefs(self):
        """Load user preferences from file."""
        if os.path.exists(USER_PREFS_FILE):
            try:
                data = load_json(USER_PREFS_FILE)
                return data if isinstance(data, dict) else {"entry_mode": "quick"}
            except:
                return {"entry_mode": "quick"}
        return {"entry_mode": "quick"}
    
    def save_user_prefs(self):
        """Save user preferences to file."""
        save_json(USER_PREFS_FILE, self.user_prefs)
    
    def get_entry_mode(self):
        """Get the last used entry mode (quick or detailed)."""
        return self.user_prefs.get("entry_mode", "quick")
    
    def set_entry_mode(self, mode):
        """Set the entry mode preference."""
        self.user_prefs["entry_mode"] = mode
        self.save_user_prefs()
    
    def _load_stats_cache(self):
        """Load computed stats cache from file."""
        if os.path.exists(STATS_CACHE_FILE):
            try:
                return load_json(STATS_CACHE_FILE)
            except:
                return {}
        return {}
    
    def save_stats_cache(self):
        """Save stats cache to file."""
        save_json(STATS_CACHE_FILE, self.stats_cache)
    
    def invalidate_stats_cache(self):
        """Mark stats cache as invalid (needs recomputation)."""
        self.stats_cache["valid"] = False
        self.save_stats_cache()
    
    def _load_pdf_annotations(self):
        """Load PDF annotations (highlights, notes) from file."""
        if os.path.exists(PDF_ANNOTATIONS_FILE):
            try:
                data = load_json(PDF_ANNOTATIONS_FILE)
                return data if isinstance(data, dict) else {}
            except:
                return {}
        return {}
    
    def _load_page_bookmarks(self):
        """Load bookmarked page numbers from file."""
        if os.path.exists(PAGE_BOOKMARKS_FILE):
            try:
                data = load_json(PAGE_BOOKMARKS_FILE)
                return data if isinstance(data, list) else []
            except:
                return []
        return []

    # ---- Courses ----
    def get_courses(self):
        return self.courses

    def get_course_by_name(self, name):
        return next((c for c in self.courses if c["name"] == name), None)

    def add_course(self, course_data):
        par_total = sum(course_data["pars"])
        for box in course_data["tee_boxes"]:
            hc = (box["slope"] / 113) * (box["rating"] - par_total)
            box["handicap"] = round(hc, 1)
        # Ensure yardages field exists (backward compatibility)
        if "yardages" not in course_data:
            course_data["yardages"] = {}
        self.courses.append(course_data)
        save_json(COURSES_FILE, self.courses)

    def update_course(self, original_name, course_data):
        par_total = sum(course_data["pars"])
        for box in course_data["tee_boxes"]:
            hc = (box["slope"] / 113) * (box["rating"] - par_total)
            box["handicap"] = round(hc, 1)
        # Ensure yardages field exists (backward compatibility)
        if "yardages" not in course_data:
            course_data["yardages"] = {}
        for i, c in enumerate(self.courses):
            if c["name"] == original_name:
                self.courses[i] = course_data
                break
        save_json(COURSES_FILE, self.courses)

    def delete_course(self, name):
        """Remove a course by name."""
        self.courses = [c for c in self.courses if c["name"] != name]
        save_json(COURSES_FILE, self.courses)

    def get_clubs_list(self):
        """Return list of unique club names."""
        return list(set(c.get("club", "") for c in self.courses if c.get("club")))

    def get_courses_by_club(self, club_name):
        """Return courses belonging to a specific club."""
        return [c for c in self.courses if c.get("club") == club_name]

    def get_course_yardages(self, course_name, tee_color):
        """Get yardages for a specific course and tee box."""
        course = self.get_course_by_name(course_name)
        if not course:
            return None
        yardages = course.get("yardages", {})
        return yardages.get(tee_color, [])

    def get_course_total_yardage(self, course_name, tee_color, holes_choice="full_18"):
        """Get total yardage for specified holes."""
        yardages = self.get_course_yardages(course_name, tee_color)
        if not yardages:
            return None
        
        if holes_choice == "front_9":
            return sum(yardages[:9]) if len(yardages) >= 9 else sum(yardages)
        elif holes_choice == "back_9":
            return sum(yardages[9:18]) if len(yardages) >= 18 else sum(yardages[:9])
        else:
            return sum(yardages)

    def calculate_course_handicap(self, course_name, tee_color, holes_choice="full_18"):
        """
        Calculate Course Handicap for a specific course/tee combination.
        
        Formula (USGA/WHS): Course Handicap = Handicap Index × (Slope / 113) + (Course Rating - Par)
        
        For 9 holes, the course handicap is halved.
        
        Returns: (course_handicap, target_score) tuple, or (None, None) if no handicap established
        """
        handicap_index = self.calculate_handicap_index()
        if handicap_index is None:
            return None, None
        
        course = self.get_course_by_name(course_name)
        if not course:
            return None, None
        
        box = next((b for b in course["tee_boxes"] if b["color"] == tee_color), None)
        if not box:
            return None, None
        
        slope = box["slope"]
        rating = box["rating"]
        par_total = sum(course["pars"])
        
        # Full 18-hole course handicap
        course_handicap = handicap_index * (slope / 113) + (rating - par_total)
        
        if holes_choice in ["front_9", "back_9"]:
            # For 9 holes, halve the course handicap and adjust par
            course_handicap = course_handicap / 2
            if holes_choice == "front_9":
                par = sum(course["pars"][:9])
            else:
                par = sum(course["pars"][9:]) if len(course["pars"]) > 9 else sum(course["pars"][:9])
        else:
            par = par_total
        
        course_handicap = round(course_handicap, 1)
        target_score = par + round(course_handicap)
        
        return course_handicap, target_score

    # ---- Rounds ----
    def get_rounds(self):
        return self.rounds

    def add_round(self, round_data):
        course = self.get_course_by_name(round_data["course_name"])
        if not course:
            return
        box = next(b for b in course["tee_boxes"] if b["color"] == round_data["tee_color"])
        par = sum(course["pars"])
        round_data["target_score"] = par + round(box["handicap"])
        round_data["tee_rating"] = box["rating"]
        round_data["tee_slope"] = box["slope"]
        round_data["par"] = par
        # Add timestamp if not present
        if "date" not in round_data:
            round_data["date"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.rounds.append(round_data)
        save_json(ROUNDS_FILE, self.rounds)
        self.invalidate_stats_cache()  # Stats need recomputation

    def delete_round(self, index):
        """Delete a round by its index."""
        if 0 <= index < len(self.rounds):
            del self.rounds[index]
            save_json(ROUNDS_FILE, self.rounds)
            self.invalidate_stats_cache()

    def update_round(self, index, round_data):
        """Update a round at the given index."""
        if 0 <= index < len(self.rounds):
            self.rounds[index] = round_data
            save_json(ROUNDS_FILE, self.rounds)
            self.invalidate_stats_cache()

    def get_filtered_rounds(self, round_type="all", sort_by="recent"):
        """
        Filter and sort rounds.
        round_type: 'all', 'solo', 'scramble'
        sort_by: 'recent', 'best', 'worst'
        """
        rounds_with_idx = [(i, r) for i, r in enumerate(self.rounds)]

        # Filter by type
        if round_type == "solo":
            rounds_with_idx = [(i, r) for i, r in rounds_with_idx
                              if r.get("round_type", "solo") == "solo"]
        elif round_type == "scramble":
            rounds_with_idx = [(i, r) for i, r in rounds_with_idx
                              if r.get("round_type") == "scramble"]

        # Sort
        if sort_by == "recent":
            rounds_with_idx.sort(key=lambda x: x[1].get("date", ""), reverse=True)
        elif sort_by == "best":
            rounds_with_idx.sort(key=lambda x: x[1].get("total_score", 999))
        elif sort_by == "worst":
            rounds_with_idx.sort(key=lambda x: x[1].get("total_score", 0), reverse=True)

        return rounds_with_idx

    # ---- Aggregates ----
    def calculate_9hole_expected_differential(self, handicap_index):
        """
        Calculate expected 9-hole differential based on current handicap index.
        Formula from 2024 WHS rules: Expected Score = (0.52 × Handicap_Index) + 1.2
        """
        if handicap_index is None:
            return None
        return (0.52 * handicap_index) + 1.2

    def calculate_score_differential(self, round_data, current_handicap=None):
        """
        Calculate score differential for a round.
        For 9-hole rounds, uses the 2024 WHS method with expected score.
        """
        try:
            holes_played = round_data.get("holes_played", 18)
            total_score = round_data["total_score"]
            tee_rating = round_data["tee_rating"]
            tee_slope = round_data["tee_slope"]

            if holes_played == 18:
                # Standard 18-hole calculation
                diff = (113 * (total_score - tee_rating)) / tee_slope
            else:
                # 9-hole calculation (2024 WHS rules)
                # First calculate 9-hole differential
                nine_hole_diff = (113 * (total_score - tee_rating)) / tee_slope

                # Add expected differential for the unplayed 9
                if current_handicap is not None:
                    expected_diff = self.calculate_9hole_expected_differential(current_handicap)
                    diff = nine_hole_diff + expected_diff
                else:
                    # If no handicap established, double the 9-hole diff as approximation
                    diff = nine_hole_diff * 2

            return round(diff, 1)
        except (ZeroDivisionError, KeyError):
            return None

    def calculate_handicap_index(self):
        """
        Calculate handicap index using serious, solo rounds (both 9 and 18 hole).
        Uses the official USGA/WHS formula with the handicap table adjustments.
        9-hole rounds are converted to 18-hole equivalents using expected score.
        
        When no 18-hole rounds exist, 9-hole rounds are combined in pairs or
        doubled (as approximation) to establish an initial handicap.
        """
        # Collect all eligible rounds separated by hole count
        rounds_18 = []
        rounds_9 = []
        
        for r in self.rounds:
            is_solo = r.get("round_type", "solo") == "solo"
            is_serious = r.get("is_serious", False)
            
            if is_solo and is_serious:
                holes = r.get("holes_played", 18)
                if holes == 18:
                    rounds_18.append(r)
                elif holes == 9:
                    rounds_9.append(r)
        
        # First pass: calculate differentials for 18-hole rounds to establish base handicap
        diffs_18 = []
        for r in rounds_18:
            diff = self.calculate_score_differential(r)
            if diff is not None:
                diffs_18.append(diff)
        
        # Calculate preliminary handicap from 18-hole rounds if we have enough
        preliminary_handicap = None
        if len(diffs_18) >= 3:
            sorted_diffs = sorted(diffs_18)
            preliminary_handicap = self._apply_handicap_table(sorted_diffs)
        
        # If no preliminary handicap from 18-hole rounds, try to establish one from 9-hole rounds
        # by using the doubling approximation method
        if preliminary_handicap is None and len(rounds_9) >= 3:
            # Calculate approximate differentials by doubling 9-hole diffs
            approx_diffs = []
            for r in rounds_9:
                diff = self.calculate_score_differential(r, current_handicap=None)
                if diff is not None:
                    approx_diffs.append(diff)
            
            if len(approx_diffs) >= 3:
                sorted_approx = sorted(approx_diffs)
                preliminary_handicap = self._apply_handicap_table(sorted_approx)
        
        # Second pass: include all rounds using the preliminary handicap (if available)
        all_diffs = []
        for r in rounds_18:
            diff = self.calculate_score_differential(r)
            if diff is not None:
                all_diffs.append(diff)
        
        for r in rounds_9:
            # Use preliminary handicap if available, otherwise use doubling approximation
            diff = self.calculate_score_differential(r, preliminary_handicap)
            if diff is not None:
                all_diffs.append(diff)
        
        if len(all_diffs) < 3:
            return None
        
        all_diffs.sort()
        return self._apply_handicap_table(all_diffs)

    def _apply_handicap_table(self, sorted_diffs):
        """Apply the USGA handicap table to sorted differentials."""
        n = len(sorted_diffs)

        if n < 3:
            return None

        if n == 3:
            idx = sorted_diffs[0] - 2.0
        elif n == 4:
            idx = sorted_diffs[0] - 1.0
        elif n == 5:
            idx = sorted_diffs[0]
        elif n == 6:
            idx = mean(sorted_diffs[:2]) - 1.0
        elif n <= 8:
            idx = mean(sorted_diffs[:2])
        elif n <= 11:
            idx = mean(sorted_diffs[:3])
        elif n <= 14:
            idx = mean(sorted_diffs[:4])
        elif n <= 16:
            idx = mean(sorted_diffs[:5])
        elif n <= 18:
            idx = mean(sorted_diffs[:6])
        elif n == 19:
            idx = mean(sorted_diffs[:7])
        else:
            idx = mean(sorted_diffs[:8])

        # Apply 0.96 multiplier (bonus for improvement)
        return round(idx * 0.96, 1)

    def get_handicap_rounds_count(self):
        """Return count of rounds eligible for handicap calculation."""
        count_18 = 0
        count_9 = 0
        for r in self.rounds:
            is_solo = r.get("round_type", "solo") == "solo"
            is_serious = r.get("is_serious", False)
            if is_solo and is_serious:
                if r.get("holes_played") == 18:
                    count_18 += 1
                elif r.get("holes_played") == 9:
                    count_9 += 1
        return {"18_hole": count_18, "9_hole": count_9, "total": count_18 + count_9}

    def get_total_holes_played(self):
        """Return total holes played for handicap-eligible rounds."""
        total = 0
        for r in self.rounds:
            is_solo = r.get("round_type", "solo") == "solo"
            is_serious = r.get("is_serious", False)
            if is_solo and is_serious:
                total += r.get("holes_played", 0)
        return total

    def get_best_round(self, holes_filter=None):
        """
        Get best serious solo round.
        holes_filter: None for any, 18 for 18-hole only, 9 for 9-hole only
        """
        serious_rounds = [r for r in self.rounds
                          if r.get("is_serious")
                          and r.get("round_type", "solo") == "solo"]

        if holes_filter:
            serious_rounds = [r for r in serious_rounds if r.get("holes_played") == holes_filter]

        if not serious_rounds:
            return None

        # For comparison, normalize to score vs par
        def score_vs_par(r):
            return r["total_score"] - r.get("par", 36 if r.get("holes_played") == 9 else 72)

        return min(serious_rounds, key=score_vs_par)

    def get_score_differentials(self):
        """Return list of all score differentials for serious solo rounds."""
        # Get current handicap for 9-hole calculations
        current_handicap = self.calculate_handicap_index()

        diffs = []
        for r in self.rounds:
            is_solo = r.get("round_type", "solo") == "solo"
            is_serious = r.get("is_serious", False)

            if is_solo and is_serious:
                holes = r.get("holes_played", 18)
                if holes == 18:
                    diff = self.calculate_score_differential(r)
                elif holes == 9 and current_handicap is not None:
                    diff = self.calculate_score_differential(r, current_handicap)
                else:
                    continue

                if diff is not None:
                    diffs.append({
                        "diff": diff,
                        "course": r["course_name"],
                        "score": r["total_score"],
                        "holes": holes,
                        "date": r.get("date", "N/A")
                    })

        return sorted(diffs, key=lambda x: x["diff"])

    # ---- Club Distances ----
    def get_clubs(self):
        """Return all saved clubs with distances."""
        return self.clubs

    def add_club(self, club_data):
        """
        Add a new club.
        club_data: {"name": "7 Iron", "distance": 150, "notes": ""}
        """
        # Check for duplicate
        existing = next((c for c in self.clubs if c["name"].lower() == club_data["name"].lower()), None)
        if existing:
            return False
        self.clubs.append(club_data)
        save_json(CLUBS_FILE, self.clubs)
        return True

    def update_club(self, original_name, club_data):
        """Update an existing club."""
        for i, c in enumerate(self.clubs):
            if c["name"] == original_name:
                self.clubs[i] = club_data
                save_json(CLUBS_FILE, self.clubs)
                return True
        return False

    def delete_club(self, name):
        """Delete a club by name."""
        self.clubs = [c for c in self.clubs if c["name"] != name]
        save_json(CLUBS_FILE, self.clubs)

    def get_clubs_sorted_by_distance(self):
        """Return clubs sorted by distance (longest first)."""
        return sorted(self.clubs, key=lambda c: c.get("distance", 0), reverse=True)

    # ---- Rulebook Management (PDF-based) ----
    def _load_rulebook(self):
        """Load the rulebook from PDF."""
        return PDFRulebook(RULEBOOK_PDF)
    
    def is_rulebook_available(self):
        """Check if rulebook PDF is loaded."""
        return self.rulebook.is_available()

    def get_rulebook(self):
        """Return the rulebook object."""
        return self.rulebook

    def get_rulebook_version(self):
        """Return the rulebook version info."""
        return self.rulebook.get_version()

    def search_rulebook(self, query):
        """
        Search the rulebook for rules matching the query.
        Returns list of matching rules with section info.
        """
        return self.rulebook.search(query)
    
    def search_rulebook_pages(self, query):
        """
        Search PDF pages directly for the query.
        Returns list of page matches with snippets.
        """
        return self.rulebook.search_pdf_pages(query)

    def get_rule_by_id(self, rule_id):
        """Get a specific rule by its ID."""
        return self.rulebook.get_rule_by_id(rule_id)

    def get_all_sections(self):
        """Return list of all sections for navigation."""
        return [(s[0], s[1]) for s in self.rulebook.get_all_sections()]
    
    def get_all_sections_with_pages(self):
        """Return list of all sections with page numbers."""
        return self.rulebook.get_all_sections()

    def get_section_rules(self, section_id):
        """Get all rules in a specific section."""
        return self.rulebook.get_section_rules(section_id)
    
    def get_page_content(self, page_num):
        """Get the content of a specific PDF page."""
        return self.rulebook.get_page_content(page_num)
    
    def get_total_pages(self):
        """Get total number of pages in the rulebook."""
        return self.rulebook.get_total_pages()

    def set_rulebook_path(self, pdf_path):
        """
        Change the rulebook PDF path.
        This allows for rulebook updates without code changes.
        """
        if os.path.exists(pdf_path):
            # Close old PDF if open
            if self.rulebook:
                self.rulebook.close()
            
            # Copy to data directory
            import shutil
            shutil.copy(pdf_path, RULEBOOK_PDF)
            
            # Reload rulebook
            self.rulebook = PDFRulebook(RULEBOOK_PDF)
            self.rulebook.clear_cache()  # Force re-parsing
            return True
        return False

    def import_rulebook_from_file(self, filepath):
        """Import a rulebook from a PDF file."""
        try:
            return self.set_rulebook_path(filepath)
        except Exception as e:
            print(f"Error importing rulebook: {e}")
            return False

    # ---- Bookmarks ----
    def get_bookmarks(self):
        """Return all bookmarked rules."""
        return self.bookmarks

    def add_bookmark(self, rule_id):
        """Add a rule to bookmarks."""
        if rule_id not in self.bookmarks:
            self.bookmarks.append(rule_id)
            save_json(BOOKMARKS_FILE, self.bookmarks)
            return True
        return False

    def remove_bookmark(self, rule_id):
        """Remove a rule from bookmarks."""
        if rule_id in self.bookmarks:
            self.bookmarks.remove(rule_id)
            save_json(BOOKMARKS_FILE, self.bookmarks)
            return True
        return False

    def is_bookmarked(self, rule_id):
        """Check if a rule is bookmarked."""
        return rule_id in self.bookmarks

    # ---- Rule Notes ----
    def get_rule_notes(self, rule_id):
        """Get user notes for a specific rule."""
        return self.rule_notes.get(rule_id, "")

    def set_rule_notes(self, rule_id, notes):
        """Set user notes for a specific rule."""
        if notes.strip():
            self.rule_notes[rule_id] = notes.strip()
        elif rule_id in self.rule_notes:
            del self.rule_notes[rule_id]
        save_json(RULE_NOTES_FILE, self.rule_notes)

    def get_all_notes(self):
        """Return all rules with notes."""
        return self.rule_notes

    # ---- PDF Annotations (ForeFlight-style) ----
    def get_pdf_annotations(self):
        """Get all PDF annotations (highlights, notes by page)."""
        return self.pdf_annotations
    
    def save_pdf_annotations(self, annotations):
        """Save PDF annotations to file."""
        self.pdf_annotations = annotations
        save_json(PDF_ANNOTATIONS_FILE, annotations)
    
    def get_page_annotations(self, page_num):
        """Get annotations for a specific page."""
        return self.pdf_annotations.get(str(page_num), [])
    
    def add_page_annotation(self, page_num, annotation):
        """Add an annotation to a specific page."""
        page_key = str(page_num)
        if page_key not in self.pdf_annotations:
            self.pdf_annotations[page_key] = []
        self.pdf_annotations[page_key].append(annotation)
        save_json(PDF_ANNOTATIONS_FILE, self.pdf_annotations)
    
    def clear_page_annotations(self, page_num):
        """Clear all annotations from a specific page."""
        page_key = str(page_num)
        if page_key in self.pdf_annotations:
            del self.pdf_annotations[page_key]
            save_json(PDF_ANNOTATIONS_FILE, self.pdf_annotations)

    # ---- Page Bookmarks (ForeFlight-style) ----
    def get_page_bookmarks(self):
        """Get list of bookmarked page numbers."""
        return self.page_bookmarks
    
    def save_page_bookmarks(self, bookmarks):
        """Save page bookmarks to file."""
        self.page_bookmarks = sorted(list(set(bookmarks)))
        save_json(PAGE_BOOKMARKS_FILE, self.page_bookmarks)
    
    def add_page_bookmark(self, page_num):
        """Add a page to bookmarks."""
        if page_num not in self.page_bookmarks:
            self.page_bookmarks.append(page_num)
            self.page_bookmarks.sort()
            save_json(PAGE_BOOKMARKS_FILE, self.page_bookmarks)
            return True
        return False
    
    def remove_page_bookmark(self, page_num):
        """Remove a page from bookmarks."""
        if page_num in self.page_bookmarks:
            self.page_bookmarks.remove(page_num)
            save_json(PAGE_BOOKMARKS_FILE, self.page_bookmarks)
            return True
        return False
    
    def is_page_bookmarked(self, page_num):
        """Check if a page is bookmarked."""
        return page_num in self.page_bookmarks

    # ---- Statistics ----
    def get_statistics(self):
        """Return various statistics about the player's rounds."""
        total_rounds = len(self.rounds)
        serious_rounds = len([r for r in self.rounds if r.get("is_serious")])
        solo_rounds = len([r for r in self.rounds if r.get("round_type", "solo") == "solo"])
        scramble_rounds = len([r for r in self.rounds if r.get("round_type") == "scramble"])

        # Count by holes
        rounds_18 = len([r for r in self.rounds if r.get("holes_played") == 18])
        rounds_9 = len([r for r in self.rounds if r.get("holes_played") == 9])

        # Average score for serious 18-hole rounds
        serious_18 = [r for r in self.rounds
                      if r.get("is_serious") and r.get("holes_played") == 18]
        avg_score_18 = None
        if serious_18:
            avg_score_18 = round(mean(r["total_score"] for r in serious_18), 1)

        # Average score for serious 9-hole rounds
        serious_9 = [r for r in self.rounds
                     if r.get("is_serious") and r.get("holes_played") == 9]
        avg_score_9 = None
        if serious_9:
            avg_score_9 = round(mean(r["total_score"] for r in serious_9), 1)

        handicap_counts = self.get_handicap_rounds_count()
        total_holes = self.get_total_holes_played()

        return {
            "total_rounds": total_rounds,
            "serious_rounds": serious_rounds,
            "solo_rounds": solo_rounds,
            "scramble_rounds": scramble_rounds,
            "rounds_18": rounds_18,
            "rounds_9": rounds_9,
            "avg_score_18": avg_score_18,
            "avg_score_9": avg_score_9,
            "handicap_eligible_18": handicap_counts["18_hole"],
            "handicap_eligible_9": handicap_counts["9_hole"],
            "total_holes_played": total_holes
        }

    def get_advanced_statistics(self):
        """
        Calculate advanced statistics from detailed round data.
        Returns GIR, putting stats, strokes-to-green by par type, club usage, etc.
        """
        # Check cache first
        if self.stats_cache.get("valid") and self.stats_cache.get("advanced_stats"):
            return self.stats_cache["advanced_stats"]
        
        stats = {
            "gir": {"par3": [], "par4": [], "par5": [], "overall": []},
            "putts": {"par3": [], "par4": [], "par5": [], "overall": []},
            "strokes_to_green": {"par3": [], "par4": [], "par5": []},
            "three_putt_count": 0,
            "one_putt_count": 0,
            "total_holes_with_putts": 0,
            "club_usage": {},
            "scramble_opportunities": 0,
            "scramble_successes": 0,
        }
        
        for rd in self.rounds:
            if not rd.get("detailed_stats"):
                continue
            
            course = self.get_course_by_name(rd["course_name"])
            if not course:
                continue
            
            pars = course["pars"]
            detailed = rd["detailed_stats"]
            
            for hole_idx, hole_data in enumerate(detailed):
                if hole_idx >= len(pars):
                    continue
                    
                par = pars[hole_idx]
                par_key = f"par{par}" if par in [3, 4, 5] else None
                
                strokes_to_green = hole_data.get("strokes_to_green")
                putts = hole_data.get("putts")
                clubs_used = hole_data.get("clubs_used", [])
                score = hole_data.get("score")
                
                # GIR calculation
                if strokes_to_green is not None:
                    gir_target = par - 2  # Par 3: 1 stroke, Par 4: 2 strokes, Par 5: 3 strokes
                    is_gir = strokes_to_green <= gir_target
                    stats["gir"]["overall"].append(1 if is_gir else 0)
                    if par_key:
                        stats["gir"][par_key].append(1 if is_gir else 0)
                        stats["strokes_to_green"][par_key].append(strokes_to_green)
                    
                    # Scramble tracking (missed GIR but made bogey or better)
                    if not is_gir and score is not None:
                        stats["scramble_opportunities"] += 1
                        if score <= par + 1:  # Bogey or better
                            stats["scramble_successes"] += 1
                
                # Putting stats
                if putts is not None:
                    stats["putts"]["overall"].append(putts)
                    stats["total_holes_with_putts"] += 1
                    if par_key:
                        stats["putts"][par_key].append(putts)
                    
                    if putts >= 3:
                        stats["three_putt_count"] += 1
                    if putts == 1:
                        stats["one_putt_count"] += 1
                
                # Club usage tracking (exclude putter from ranking)
                for club in clubs_used:
                    if club.lower() != "putter":
                        stats["club_usage"][club] = stats["club_usage"].get(club, 0) + 1
        
        # Calculate averages and percentages
        result = {
            "gir_overall": self._calc_percentage(stats["gir"]["overall"]),
            "gir_par3": self._calc_percentage(stats["gir"]["par3"]),
            "gir_par4": self._calc_percentage(stats["gir"]["par4"]),
            "gir_par5": self._calc_percentage(stats["gir"]["par5"]),
            "avg_putts_overall": self._calc_average(stats["putts"]["overall"]),
            "avg_putts_par3": self._calc_average(stats["putts"]["par3"]),
            "avg_putts_par4": self._calc_average(stats["putts"]["par4"]),
            "avg_putts_par5": self._calc_average(stats["putts"]["par5"]),
            "avg_strokes_to_green_par3": self._calc_average(stats["strokes_to_green"]["par3"]),
            "avg_strokes_to_green_par4": self._calc_average(stats["strokes_to_green"]["par4"]),
            "avg_strokes_to_green_par5": self._calc_average(stats["strokes_to_green"]["par5"]),
            "three_putt_rate": round(stats["three_putt_count"] / stats["total_holes_with_putts"] * 100, 1) if stats["total_holes_with_putts"] > 0 else None,
            "one_putt_rate": round(stats["one_putt_count"] / stats["total_holes_with_putts"] * 100, 1) if stats["total_holes_with_putts"] > 0 else None,
            "scramble_rate": round(stats["scramble_successes"] / stats["scramble_opportunities"] * 100, 1) if stats["scramble_opportunities"] > 0 else None,
            "club_usage": stats["club_usage"],
            "total_holes_tracked": stats["total_holes_with_putts"],
            "scramble_opportunities": stats["scramble_opportunities"],
            "scramble_successes": stats["scramble_successes"],
        }
        
        # Cache the result
        self.stats_cache["advanced_stats"] = result
        self.stats_cache["valid"] = True
        self.save_stats_cache()
        
        return result
    
    def _calc_percentage(self, values):
        """Calculate percentage from a list of 0s and 1s."""
        if not values:
            return None
        return round(sum(values) / len(values) * 100, 1)
    
    def _calc_average(self, values):
        """Calculate average from a list of numbers."""
        if not values:
            return None
        return round(mean(values), 2)
    
    def get_club_analytics(self):
        """
        Analyze club usage patterns.
        Returns clubs ranked by usage, rarely used clubs, and category breakdown.
        """
        adv_stats = self.get_advanced_statistics()
        club_usage = adv_stats.get("club_usage", {})
        
        if not club_usage:
            return {
                "ranked_clubs": [],
                "rarely_used": [],
                "never_used": [],
                "category_breakdown": {},
                "total_shots": 0
            }
        
        total_shots = sum(club_usage.values())
        
        # Rank clubs by usage (most to least)
        ranked = sorted(club_usage.items(), key=lambda x: x[1], reverse=True)
        ranked_clubs = [
            {"name": name, "count": count, "percentage": round(count / total_shots * 100, 1)}
            for name, count in ranked
        ]
        
        # Find rarely used clubs (< 3% of shots)
        rarely_used = [c for c in ranked_clubs if c["percentage"] < 3]
        
        # Find clubs in bag that were never used
        bag_clubs = [c["name"] for c in self.clubs if c["name"].lower() != "putter"]
        used_clubs = set(club_usage.keys())
        never_used = [c for c in bag_clubs if c not in used_clubs]
        
        # Category breakdown
        category_breakdown = {}
        for club_name, count in club_usage.items():
            cat_info = CLUB_CATEGORIES.get(club_name, {"category": "other"})
            cat = cat_info["category"]
            category_breakdown[cat] = category_breakdown.get(cat, 0) + count
        
        return {
            "ranked_clubs": ranked_clubs,
            "rarely_used": rarely_used,
            "never_used": never_used,
            "category_breakdown": category_breakdown,
            "total_shots": total_shots
        }
    
    def get_stroke_leak_analysis(self):
        """
        Analyze where the player is losing the most strokes.
        Returns insights about tee-to-green vs putting performance.
        """
        adv_stats = self.get_advanced_statistics()
        
        insights = []
        
        # Check strokes to green vs par expectations
        avg_stg_par4 = adv_stats.get("avg_strokes_to_green_par4")
        if avg_stg_par4 is not None:
            excess = avg_stg_par4 - 2  # Expectation is 2 for par 4
            if excess > 1:
                insights.append({
                    "area": "approach",
                    "severity": "high" if excess > 2 else "medium",
                    "message": f"On Par 4s, you're averaging {avg_stg_par4:.1f} strokes to reach the green (target: 2)",
                    "stat": avg_stg_par4
                })
        
        avg_stg_par3 = adv_stats.get("avg_strokes_to_green_par3")
        if avg_stg_par3 is not None:
            excess = avg_stg_par3 - 1
            if excess > 0.5:
                insights.append({
                    "area": "tee_shots_par3",
                    "severity": "high" if excess > 1 else "medium",
                    "message": f"On Par 3s, you're averaging {avg_stg_par3:.1f} strokes to reach the green (target: 1)",
                    "stat": avg_stg_par3
                })
        
        # Check putting
        three_putt_rate = adv_stats.get("three_putt_rate")
        if three_putt_rate is not None and three_putt_rate > 10:
            insights.append({
                "area": "putting",
                "severity": "high" if three_putt_rate > 20 else "medium",
                "message": f"3-putt rate is {three_putt_rate:.1f}% ({adv_stats.get('total_holes_tracked', 0)} holes tracked)",
                "stat": three_putt_rate
            })
        
        avg_putts = adv_stats.get("avg_putts_overall")
        if avg_putts is not None and avg_putts > 2.1:
            insights.append({
                "area": "putting_avg",
                "severity": "medium",
                "message": f"Averaging {avg_putts:.2f} putts per hole (tour avg: ~1.8)",
                "stat": avg_putts
            })
        
        # GIR insights
        gir_overall = adv_stats.get("gir_overall")
        if gir_overall is not None and gir_overall < 30:
            insights.append({
                "area": "gir",
                "severity": "high" if gir_overall < 20 else "medium",
                "message": f"GIR is {gir_overall:.1f}% (amateur target: 30-40%)",
                "stat": gir_overall
            })
        
        # Sort by severity
        severity_order = {"high": 0, "medium": 1, "low": 2}
        insights.sort(key=lambda x: severity_order.get(x["severity"], 2))
        
        return insights


# ---- Scorecard Export Helper Functions ----
def generate_scorecard_data(backend, round_data):
    """
    Generate formatted scorecard data for export.
    Returns a dictionary with all data needed for PDF/image export.
    """
    course = backend.get_course_by_name(round_data["course_name"])
    pars = course["pars"] if course else [4] * len(round_data.get("scores", []))
    
    # Get yardages if available
    yardages = []
    if course:
        tee_color = round_data.get("tee_color", "")
        yardages = course.get("yardages", {}).get(tee_color, [])
    
    scores = round_data.get("scores", [])
    diff = round_data.get("total_score", 0) - round_data.get("par", 72)
    diff_str = f"+{diff}" if diff > 0 else str(diff)
    
    # Calculate front/back 9 totals
    front_9_scores = [s for s in scores[:9] if s is not None]
    back_9_scores = [s for s in scores[9:18] if s is not None] if len(scores) > 9 else []
    front_9_pars = pars[:9]
    back_9_pars = pars[9:18] if len(pars) > 9 else []
    front_9_yards = yardages[:9] if len(yardages) >= 9 else yardages
    back_9_yards = yardages[9:18] if len(yardages) >= 18 else []
    
    return {
        "course_name": round_data.get("course_name", "Unknown Course"),
        "club_name": course.get("club", "") if course else "",
        "date": round_data.get("date", "N/A"),
        "tee_color": round_data.get("tee_color", "N/A"),
        "holes_played": round_data.get("holes_played", 18),
        "holes_choice": round_data.get("holes_choice", "full_18"),
        "total_score": round_data.get("total_score", 0),
        "par": round_data.get("par", 72),
        "diff_str": diff_str,
        "target_score": round_data.get("target_score", "N/A"),
        "round_type": round_data.get("round_type", "solo"),
        "is_serious": round_data.get("is_serious", False),
        "notes": round_data.get("notes", ""),
        "pars": pars,
        "scores": scores,
        "yardages": yardages,
        "front_9": {
            "pars": front_9_pars,
            "scores": front_9_scores,
            "yardages": front_9_yards,
            "par_total": sum(front_9_pars),
            "score_total": sum(front_9_scores) if front_9_scores else 0,
            "yards_total": sum(front_9_yards) if front_9_yards else 0
        },
        "back_9": {
            "pars": back_9_pars,
            "scores": back_9_scores,
            "yardages": back_9_yards,
            "par_total": sum(back_9_pars) if back_9_pars else 0,
            "score_total": sum(back_9_scores) if back_9_scores else 0,
            "yards_total": sum(back_9_yards) if back_9_yards else 0
        }
    }