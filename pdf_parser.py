import pdfplumber
import re
from datetime import datetime

WELD_ID_REGEX = re.compile(r"(\d)([A-Z]{2,3})([A-Z])(\d+)([A-Z]*)?$")

def clean_text(text):
    return text.replace('\n', ' ').strip() if text else ''

def parse_weld_id(weld_id_raw):
    match = WELD_ID_REGEX.match(weld_id_raw)
    if not match:
        return None
    spread, weld_type_raw, rig_id, weld_num, suffix = match.groups()
    weld_type = weld_type_raw
    if len(weld_type_raw) > 2:
         weld_type = weld_type_raw[:2]
         rig_id = weld_type_raw[2]
    return {
        'spread': int(spread), 'weld_type': weld_type, 'rig_id': rig_id,
        'weld_num_only': weld_num, 'suffix': suffix or ''
    }

def process_table(table, report_info, column_map):
    welds = []
    for row in table:
        try:
            weld_id_raw = clean_text(row[column_map['weld_id']])
            parsed_id_components = parse_weld_id(weld_id_raw)
            if not parsed_id_components:
                continue

            weld_data = report_info.copy()
            weld_data['weld_id'] = weld_id_raw
            weld_data.update(parsed_id_components)

            suffix = parsed_id_components.get('suffix', '').upper()
            weld_data['is_repair'] = 'R' in suffix
            weld_data['is_delay_scan'] = 'D' in suffix
            # Updated: Store empty string for no suffix
            weld_data['suffix'] = suffix if suffix else ''

            result_search_space = " ".join(
                clean_text(str(cell)) for cell in row[1:4] if cell is not None
            ).upper()
            
            if 'CUT-OUT' in result_search_space:
                weld_data['result'] = 'Cut-out'
            elif 'REJECT' in result_search_space:
                weld_data['result'] = 'Reject'
            else:
                weld_data['result'] = 'Accept'
            
            if weld_data['result'] != 'Accept':
                weld_data['defect_type'] = clean_text(row[column_map.get('defect')]) if column_map.get('defect') is not None else ''
                weld_data['defect_start'] = clean_text(row[column_map.get('defect_start')]) if column_map.get('defect_start') else ''
                weld_data['defect_length'] = clean_text(row[column_map.get('defect_length')]) if column_map.get('defect_length') else ''
                weld_data['defect_depth'] = clean_text(row[column_map.get('defect_depth')]) if column_map.get('defect_depth') else ''
                weld_data['defect_height'] = clean_text(row[column_map.get('defect_height')]) if column_map.get('defect_height') else ''
            else:
                weld_data['defect_type'] = ''
                weld_data['defect_start'] = ''
                weld_data['defect_length'] = ''
                weld_data['defect_depth'] = ''
                weld_data['defect_height'] = ''

            # Convert diameter to float for AUT
            diameter_raw = clean_text(row[column_map.get('diameter')])
            try:
                weld_data['diameter'] = float(diameter_raw) if diameter_raw else None
            except (ValueError, TypeError):
                weld_data['diameter'] = None
            weld_data['wall_thickness'] = clean_text(row[column_map.get('wall_thickness')])

            weld_data['stationing'] = clean_text(row[column_map['stationing']])
            # Updated: For AUT, store comment in comments field, welder_ids empty
            if 'AUT' in report_info['nde_method']:
                comment_col = column_map.get('comment')
                weld_data['comments'] = clean_text(row[comment_col]) if comment_col is not None and len(row) > comment_col else ''
                weld_data['welder_ids'] = ''
            else:
                welder_col = column_map.get('welder_ids')
                weld_data['welder_ids'] = clean_text(row[welder_col]) if welder_col is not None and len(row) > welder_col else ''
                weld_data['comments'] = ''

            welds.append(weld_data)
        except (IndexError, TypeError):
            continue
    return welds

def parse_nde_report(pdf_file):
    report_info = {}
    all_welds = []
    
    with pdfplumber.open(pdf_file) as pdf:
        full_text = "".join(page.extract_text(x_tolerance=2, y_tolerance=2) or '' for page in pdf.pages)
        report_id_match = re.search(r"Report ID:\s*([A-Z0-9-]+)", full_text, re.IGNORECASE)
        report_date_match = re.search(r"Report Date:\s*(\w+\s\d{1,2},\s\d{4})", full_text, re.IGNORECASE)
        report_info['report_number'] = report_id_match.group(1).strip() if report_id_match else "UNKNOWN"
        report_info['inspection_date'] = datetime.strptime(report_date_match.group(1), '%B %d, %Y').date() if report_date_match else None

        generic_method = None
        if "RT DAILY WELD INSPECTION" in full_text:
            generic_method = 'RT'
            column_map = {'weld_id': 0, 'defect': 9, 'stationing': 13, 'welder_ids': 14,
                          'defect_start': 10, 'defect_length': 12, 
                          'diameter': 7, 'wall_thickness': 8}
        elif "AUT DAILY WELD INSPECTION" in full_text:
            generic_method = 'AUT'
            column_map = {'weld_id': 0, 'defect': 7, 'stationing': 15, 'comment': 17,
                          'defect_start': 10, 'defect_length': 12, 'defect_depth': 13, 'defect_height': 14,
                          'diameter': 4, 'wall_thickness': 5}
        else:
            raise ValueError("Unknown report type. Cannot find 'RT' or 'AUT' title.")

        all_tables = []
        for page in pdf.pages:
            tables = page.extract_tables()
            if tables: all_tables.extend(tables)
        
        specific_method = find_specific_nde_method(all_tables)
        report_info['nde_method'] = specific_method if specific_method else generic_method
        if report_info['nde_method'] == 'RTR':
            report_info['nde_method'] = 'RT'
        
        # For AUT: Extract fixed spread (row 58, col 5) and rig_id (row 58, col 7)
        if generic_method == 'AUT':
            fixed_spread = None
            fixed_rig_id = None
            for table in all_tables:
                if len(table) > 58:
                    fixed_row = table[58]
                    if len(fixed_row) > 7:
                        fixed_spread = clean_text(fixed_row[5])  # Cell 6 (1-indexed)
                        fixed_rig_id = clean_text(fixed_row[7])  # Cell 8 (1-indexed)
                        break
            if fixed_spread:
                report_info['spread'] = int(fixed_spread) if fixed_spread.isdigit() else None
            if fixed_rig_id:
                report_info['rig_id'] = fixed_rig_id
                
        for table in all_tables:
            all_welds.extend(process_table(table, report_info, column_map))
        
        # Override spread and rig_id for all welds if fixed values found
        if 'spread' in report_info:
            for weld in all_welds:
                weld['spread'] = report_info['spread']
        if 'rig_id' in report_info:
            for weld in all_welds:
                weld['rig_id'] = report_info['rig_id']
                
    return all_welds

def find_specific_nde_method(tables):
    for table in tables:
        cleaned_table = [[clean_text(cell) for cell in row] for row in table]
        for i, row in enumerate(cleaned_table):
            if 'NDT Type' in row:
                try:
                    header_row = row
                    ndt_col_index = header_row.index('NDT Type')
                    data_row = cleaned_table[i + 1]
                    specific_method = data_row[ndt_col_index]
                    if specific_method:
                        return specific_method
                except (ValueError, IndexError):
                    continue
    return None