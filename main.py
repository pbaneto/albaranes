import os
import gspread
import pdfplumber
import pandas as pd
import streamlit as st

from dotenv import load_dotenv
from google.oauth2 import service_account

load_dotenv()


def get_months_and_fortnights():
    """
    Generate a list of month-fortnight combinations for the entire year.
    
    Returns:
        list: Formatted strings like ["January - 1", "January - 2", "February - 1", ...]
    """
    months = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    fortnights = ["1", "2"]
    return ["Selecciona un mes..."] + [f"{month} - {fortnight}" for month in months for fortnight in fortnights] + ["Test mayo - 1"]


def format_main_table(table):
    """
    Extract and format invoice items from a PDF table structure.
    
    Processes the raw table data to extract vehicle registration, date, and item details.
    Skips empty lines and credit notes (ABONO entries).
    
    Args:
        table (list): Raw table data extracted from PDF
        
    Returns:
        list: Formatted dictionaries containing invoice item data
    """
    # Header is the first line that contains "Artículo"
    for idx, line in enumerate(table):
        if "Artículo" in line:
            header_idx = idx
            break
    else:
        # Header not found – return empty list instead of crashing
        st.warning("No se encontró la cabecera 'Artículo' en la tabla PDF.")
        return []

    result = []
    matricula = ''
    fecha = None
    
    # When found line with albaran we update matricula and fecha
    for line in table[header_idx+1:]:           
        # if all elements in line are empty, skip
        if all(item == "" for item in line):
            continue
            
        # Skip credit notes (ABONO entries)
        if any('ABONO' in item for item in line):
            continue
        
        # Extract vehicle registration and date from albaran lines
        # Format: "ALBARAN 1234567890" and "A:MATRICULA"
        albaran_idx = [idx for idx, element in enumerate(line) if element.startswith("ALBARAN")]
        matricula_idx = [idx for idx, element in enumerate(line) if element.startswith("A:")]
        if len(albaran_idx) > 0 and len(matricula_idx) > 0:
            albaran_line = line[albaran_idx[0]]
            fecha = albaran_line.split(" ")[-1]
            matricula = line[matricula_idx[0]].split(":")[1].strip()
            continue
        
        # Extract item details from data rows
        articulo = line[0]
        descripcion = line[1]
        cantidad = line[2].replace(',', '.') if line[2] else "0"
        # Normalise price and total
        precio = line[3].replace(',', '.') if line[3] else "0"
        # Strip possible % and convert decimal comma
        descuento = (
            line[4].replace('%', '').replace(',', '.') if line[4] else "0"
        )
        total = line[5].replace(',', '.') if line[5] else "0"

        result.append({
            'Matricula': matricula,
            'Fecha': fecha,
            'Artículo': articulo,
            'Descripción': descripcion,
            'Cantidad': cantidad,
            'Precio': precio,
            'Descuento': descuento,
            'Total': total
        })
    return result


def convert_str_to_float(item):
    """
    Convert Spanish number format to float.
    
    Handles format like '1.399,5' -> 1399.5 (thousands separator and comma decimal)
    
    Args:
        item (str): Number in Spanish format
        
    Returns:
        float: Converted number
    """
    item = item.replace('.', '')    # Remove thousands separator
    item = item.replace(',', '.')   # Convert decimal separator
    return float(item)


def find_total_invoice(table_total):
    """
    Extract invoice totals from the bottom table of the PDF.
    
    Args:
        table_total (list): Table containing invoice summary information
        
    Returns:
        tuple: (bruto_pdf, iva_pdf, neto_pdf) - amounts before tax, tax, and after tax
    """
    # Bruto e IVA - extract from combined string
    item = table_total[1][-3]
    bruto_pdf = convert_str_to_float(item.split(" ")[0])
    iva_pdf = convert_str_to_float(item.split(" ")[1])

    # Neto - final total amount
    neto_pdf = table_total[2][-1]
    neto_pdf = convert_str_to_float(neto_pdf)

    return bruto_pdf, iva_pdf, neto_pdf


def read_pdf(pdf_path):
    """
    Extract invoice data from PDF file and calculate totals.
    
    Processes all pages to extract item details and calculates various totals
    including shipping costs (portes) from the last page.
    
    Args:
        pdf_path (str): Path to the PDF file
        
    Returns:
        tuple: (df, before_taxes, iva, after_taxes) - DataFrame with items and calculated totals
    """
    table_settings = {
        'vertical_strategy': 'lines',
        'horizontal_strategy': 'text',
        'intersection_tolerance': 5
    }

    with pdfplumber.open(pdf_path) as pdf:
        all_items = []
        
        # Extract items from each page
        for page in pdf.pages:
            table = page.extract_table(table_settings=table_settings)
            items = format_main_table(table)

            print(f"Page {page.page_number} has {len(items)} items")
            all_items.extend(items)

            # Extract totals and shipping costs from the last page only
            if page.page_number == len(pdf.pages):       
                tables = page.extract_tables(table_settings=table_settings)

                # Calculate shipping costs (portes) from bottom table
                bottom_table = tables[-1][1]
                portes = bottom_table[0].split()
                portes = [convert_str_to_float(i) for i in portes]
                portes = sum(portes)

                # Extract official totals from PDF
                table_total = tables[-1]
                before_taxes_pdf, iva_pdf, after_taxes_pdf = find_total_invoice(table_total)

    # Convert to DataFrame and ensure numeric types
    df = pd.DataFrame(all_items)
    df['Cantidad'] = df['Cantidad'].astype(float)
    df['Precio'] = df['Precio'].astype(float)
    df['Descuento'] = df['Descuento'].astype(float)
    df['Total'] = df['Total'].astype(float)

    # Calculate totals from individual items for verification
    before_taxes = df['Total'].sum()
    iva = before_taxes * 0.21
    after_taxes = before_taxes + iva

    # Calculate totals including shipping costs
    total_with_portes = before_taxes + portes
    iva_with_portes = total_with_portes * 0.21
    after_taxes_with_portes = total_with_portes + iva_with_portes

    # Display comparison between calculated and PDF totals for verification
    print("---")
    print("Antes de impuestos, IVA, Despues de impuestos, Portes")
    print(f"Calculated from items: {before_taxes}, {iva}, {after_taxes}")
    print(f"Calculated from pdf: {before_taxes_pdf}, {iva_pdf}, {after_taxes_pdf}")
    print(f"With portes: {total_with_portes}, {iva_with_portes}, {after_taxes_with_portes}")
    print("---")

    return df, before_taxes, iva, after_taxes


def find_worksheet_by_month_fortnight(month_fortnight):
    """
    Find the Google Sheets worksheet that matches the selected month.
    
    Searches for worksheets with titles starting with the month name
    (e.g., "May - 1" matches "May 2025").
    
    Args:
        month_fortnight (str): Selection like "May - 1"
        
    Returns:
        gspread.Worksheet or None: The matching worksheet or None if not found
    """
    # Get the spreadsheet
    scopes = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    key_path = "keys/service-account.json"
    creds = service_account.Credentials.from_service_account_file(key_path, scopes=scopes)
    client = gspread.authorize(creds)
    
    spreadsheet = client.open_by_url(os.getenv("SPREADSHEET_URL"))
    try:
        # Extract month from the selection (e.g., "May - 1" -> "May")
        month = month_fortnight.split(" - ")[0]
        
        # Get all worksheets
        worksheets = spreadsheet.worksheets()
        
        # Look for a worksheet that starts with the month (case-insensitive)
        for worksheet in worksheets:
            worksheet_title = worksheet.title.lower()
            month_lower = month.lower()
            
            # Check if worksheet title starts with the month
            if worksheet_title.startswith(month_lower):
                return worksheet
        
        # If no match found, return None
        return None
    except Exception as e:
        st.error(f"Error al acceder a la hoja de cálculo: {str(e)}")
        return None


def parse_spreadsheet_data(data, fortnight):
    """
    Extract vehicle data for a specific fortnight from spreadsheet.
    
    Parses the spreadsheet structure to find the correct fortnight section
    and extracts vehicle registration and amount data.
    
    Expected format:
    Quincena 1		TOTAL Q1	1846,46	Quincena 2		TOTAL Q2	0
    Vehiculo	Cliente	Matricula	Importe	Vehiculo	Cliente	Matricula	Importe
    
    Args:
        data (list): Raw spreadsheet data
        fortnight (str): Fortnight number ("1" or "2")
        
    Returns:
        pd.DataFrame: DataFrame with Matricula and Importe_Spreadsheet columns
    """
    # Look for the fortnight header row
    fortnight_key = f"Quincena {fortnight}"
    
    # Find the row that contains the fortnight headers
    header_row = None
    fortnight_col_start = None
    
    for i, row in enumerate(data):
        for j, cell in enumerate(row):
            if fortnight_key in str(cell):
                header_row = i
                fortnight_col_start = j
                break
        if header_row is not None:
            break
    
    if header_row is None:
        return pd.DataFrame()
    
    # Calculate column positions for matricula and importe
    matricula_col = fortnight_col_start + 2
    importe_col = fortnight_col_start + 3
    
    # Extract data rows for the selected fortnight
    vehicles_data = []
    
    # Start from the row after column headers
    for i in range(header_row + 2, len(data)):
        row = data[i]
        
        # Stop if we've reached the end of the data or hit another section
        if i >= len(data) or len(row) <= max(matricula_col, importe_col):
            break
        
        # Get matricula and importe values
        matricula = str(row[matricula_col]).strip() if matricula_col < len(row) else ""
        importe_str = str(row[importe_col]).strip() if importe_col < len(row) else ""
        
        # Skip if importe is empty (as per requirement)
        if not importe_str or importe_str == "":
            continue
        
        # Parse importe handling Spanish decimal format and negative values
        try:
            importe_clean = importe_str.replace(',', '.')
            if importe_clean.startswith('-'):
                importe = -float(importe_clean[1:])
            else:
                importe = float(importe_clean)
        except ValueError:
            # Skip rows where importe can't be parsed as a number
            continue
        
        # Add the row (matricula can be empty but importe cannot)
        vehicles_data.append({
            'Matricula': matricula,
            'Importe_Spreadsheet': importe
        })
    
    df_spreadsheet = pd.DataFrame(vehicles_data)
    return df_spreadsheet


def compare_pdf_spreadsheet(df_pdf, df_spreadsheet):
    """
    Compare PDF invoice data with spreadsheet data by vehicle registration.
    
    Groups PDF data by vehicle registration and compares totals with spreadsheet amounts.
    Calculates differences and provides status indicators. For vehicles with differences,
    provides detailed item-level mapping based on amounts.
    
    Args:
        df_pdf (pd.DataFrame): PDF invoice data with columns: Matricula, Fecha, Artículo, Descripción, Cantidad, Precio, Descuento, Total
        df_spreadsheet (pd.DataFrame): Spreadsheet data with columns: Matricula, Importe_Spreadsheet
        
    Returns:
        tuple: (df_comparison, total_pdf, total_diff, detailed_differences) 
               - comparison DataFrame, totals, and detailed item differences
    """
    # Clean whitespace from Matricula columns to prevent duplicates
    df_pdf = df_pdf.copy()
    df_spreadsheet = df_spreadsheet.copy()
    df_pdf['Matricula'] = df_pdf['Matricula'].astype(str).str.strip()
    df_spreadsheet['Matricula'] = df_spreadsheet['Matricula'].astype(str).str.strip()
    
    # Group PDF data by matricula and sum totals
    df_pdf_grouped = df_pdf.groupby('Matricula')['Total'].sum().reset_index()
    df_pdf_grouped.rename(columns={'Total': 'Importe_PDF'}, inplace=True)
    
    # Group spreadsheet data by matricula and sum totals (in case there are multiple entries per vehicle)
    df_spreadsheet_grouped = df_spreadsheet.groupby('Matricula')['Importe_Spreadsheet'].sum().reset_index()
    
    # Merge the dataframes on vehicle registration
    df_comparison = pd.merge(df_pdf_grouped, df_spreadsheet_grouped, on='Matricula', how='outer')
    
    # Fill NaN values with 0 for missing entries
    df_comparison['Importe_PDF'] = df_comparison['Importe_PDF'].fillna(0)
    df_comparison['Importe_Spreadsheet'] = df_comparison['Importe_Spreadsheet'].fillna(0)
    
    # Calculate difference (PDF - Spreadsheet)
    df_comparison['Diferencia'] = df_comparison['Importe_PDF'] - df_comparison['Importe_Spreadsheet']
    
    # Add status indicators based on difference
    df_comparison['Estado'] = df_comparison['Diferencia'].apply(
        lambda x: '✅ Coincide' if abs(x) < 0.01 else ('📈 PDF Mayor' if x > 0 else '📉 Hoja de Cálculo Mayor')
    )
    
    # Find detailed differences for vehicles that don't match
    detailed_differences = {}
    
    # Get vehicles with differences (tolerance of 0.01 for floating point comparison)
    vehicles_with_differences = df_comparison[abs(df_comparison['Diferencia']) >= 0.01]['Matricula'].tolist()
    
    for matricula in vehicles_with_differences:
        # Get PDF items for this vehicle
        pdf_items = df_pdf[df_pdf['Matricula'] == matricula].copy()
        
        # Get spreadsheet amount for this vehicle (use grouped data)
        spreadsheet_amount = df_spreadsheet_grouped[df_spreadsheet_grouped['Matricula'] == matricula]['Importe_Spreadsheet'].sum()
        if len(pdf_items) == 0:
            detailed_differences[matricula] = {
                "matricula": matricula,
                "pdf_total": 0.0,
                "spreadsheet_total": spreadsheet_amount,
                "difference": -spreadsheet_amount,
                "pdf_items": [],
                "potential_matches": []
            }
        else:
            # Create detailed comparison for this vehicle
            vehicle_details = {
                'matricula': matricula,
                'pdf_total': pdf_items['Total'].sum(),
                'spreadsheet_total': spreadsheet_amount,
                'difference': pdf_items['Total'].sum() - spreadsheet_amount,
                'pdf_items': [],
                'potential_matches': []
            }
            
            # Add all PDF items for this vehicle
            for _, item in pdf_items.iterrows():
                vehicle_details['pdf_items'].append({
                    'fecha': item['Fecha'],
                    'articulo': item['Artículo'],
                    'descripcion': item['Descripción'],
                    'cantidad': item['Cantidad'],
                    'precio': item['Precio'],
                    'descuento': item['Descuento'],
                    'total': item['Total']
                })
            
            # Try to find potential matches based on amount
            if spreadsheet_amount != 0:
                # Look for PDF items that could match the spreadsheet amount
                tolerance = 0.01
                
                # Check if any single PDF item matches the spreadsheet amount
                for _, item in pdf_items.iterrows():
                    if abs(item['Total'] - spreadsheet_amount) < tolerance:
                        vehicle_details['potential_matches'].append({
                            'type': 'exact_item_match',
                            'pdf_item': {
                                'articulo': item['Artículo'],
                                'descripcion': item['Descripción'],
                                'total': item['Total']
                            },
                            'spreadsheet_amount': spreadsheet_amount,
                            'difference': item['Total'] - spreadsheet_amount
                        })
                
                # Check if combination of items could match
                if len(pdf_items) > 1:
                    # Try combinations of 2 items
                    for i in range(len(pdf_items)):
                        for j in range(i + 1, len(pdf_items)):
                            combo_total = pdf_items.iloc[i]['Total'] + pdf_items.iloc[j]['Total']
                            if abs(combo_total - spreadsheet_amount) < tolerance:
                                vehicle_details['potential_matches'].append({
                                    'type': 'combo_match',
                                    'pdf_items': [
                                        {
                                            'articulo': pdf_items.iloc[i]['Artículo'],
                                            'descripcion': pdf_items.iloc[i]['Descripción'],
                                            'total': pdf_items.iloc[i]['Total']
                                        },
                                        {
                                            'articulo': pdf_items.iloc[j]['Artículo'],
                                            'descripcion': pdf_items.iloc[j]['Descripción'],
                                            'total': pdf_items.iloc[j]['Total']
                                        }
                                    ],
                                    'combo_total': combo_total,
                                    'spreadsheet_amount': spreadsheet_amount,
                                    'difference': combo_total - spreadsheet_amount
                                })
                
                # If no exact matches found, find closest amounts
                if not vehicle_details['potential_matches']:
                    closest_item = pdf_items.loc[pdf_items['Total'].sub(spreadsheet_amount).abs().idxmin()]
                    vehicle_details['potential_matches'].append({
                        'type': 'closest_match',
                        'pdf_item': {
                            'articulo': closest_item['Artículo'],
                            'descripcion': closest_item['Descripción'],
                            'total': closest_item['Total']
                        },
                        'spreadsheet_amount': spreadsheet_amount,
                        'difference': closest_item['Total'] - spreadsheet_amount
                    })
            
            detailed_differences[matricula] = vehicle_details
    
    # Sort by absolute difference (largest differences first)
    df_comparison['Diferencia_Abs'] = abs(df_comparison['Diferencia'])
    df_comparison = df_comparison.sort_values('Diferencia_Abs', ascending=False)
    df_comparison = df_comparison.drop('Diferencia_Abs', axis=1)
    
    # Calculate totals for summary
    total_pdf = df_comparison['Importe_PDF'].sum()
    total_spreadsheet = df_spreadsheet_grouped['Importe_Spreadsheet'].sum()
    total_diff = total_pdf - total_spreadsheet
    
    return df_comparison, total_pdf, total_diff, detailed_differences


def display_detailed_differences(detailed_differences):
    """
    Display detailed item-level differences for vehicles that don't match.
    
    Args:
        detailed_differences (dict): Dictionary containing detailed difference information
    """
    if not detailed_differences:
        return
    
    st.markdown("### 🔍 Análisis Detallado de Diferencias")
    
    for matricula, details in detailed_differences.items():
        with st.expander(f"🚗 {matricula} - Diferencia: €{details['difference']:.2f}"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**📄 Artículos en PDF:**")
                for item in details['pdf_items']:
                    st.write(f"• {item['articulo']} - {item['descripcion']}")
                    st.write(f"  Cantidad: {item['cantidad']}, Precio: €{item['precio']:.2f}, Total: €{item['total']:.2f}")
                
                st.markdown(f"**Total PDF: €{details['pdf_total']:.2f}**")
            
            with col2:
                st.markdown(f"**📊 Importe Hoja de Cálculo: €{details['spreadsheet_total']:.2f}**")
                
                if details['potential_matches']:
                    st.markdown("**🎯 Posibles Coincidencias:**")
                    for match in details['potential_matches']:
                        if match['type'] == 'exact_item_match':
                            st.success(f"✅ Coincidencia exacta encontrada:")
                            st.write(f"• {match['pdf_item']['articulo']} - {match['pdf_item']['descripcion']}")
                            st.write(f"  Total: €{match['pdf_item']['total']:.2f}")
                        elif match['type'] == 'combo_match':
                            st.info(f"🔗 Combinación de artículos:")
                            for pdf_item in match['pdf_items']:
                                st.write(f"• {pdf_item['articulo']} - €{pdf_item['total']:.2f}")
                            st.write(f"  Total combinado: €{match['combo_total']:.2f}")
                        elif match['type'] == 'closest_match':
                            st.warning(f"📍 Artículo más cercano:")
                            st.write(f"• {match['pdf_item']['articulo']} - {match['pdf_item']['descripcion']}")
                            st.write(f"  Total: €{match['pdf_item']['total']:.2f}")
                            st.write(f"  Diferencia: €{match['difference']:.2f}")
                else:
                    st.error("❌ No se encontraron coincidencias potenciales")


if __name__ == "__main__":
    
    st.set_page_config(layout="wide")  
    st.title("💸 Facturación")

    # Create two main columns for the interface
    col_left, col_right = st.columns([1, 1])
    
    # Initialize session state variables
    if 'df_spreadsheet' not in st.session_state:
        st.session_state.df_spreadsheet = pd.DataFrame()
    if 'df_pdf' not in st.session_state:
        st.session_state.df_pdf = pd.DataFrame()
    if 'pdf_totals' not in st.session_state:
        st.session_state.pdf_totals = None

    # LEFT COLUMN: Month selection
    with col_left:
        st.markdown("### 📅 Selección de Mes")
        
        month_fortnight = st.selectbox("Selecciona el mes y quincena", 
                                       get_months_and_fortnights(), 
                                       index=0)

        # Only proceed if a valid month is selected
        if month_fortnight != "Selecciona un mes...":
            # Search for the worksheet that contains the selected month
            sheet = find_worksheet_by_month_fortnight(month_fortnight)
            
            if sheet is None:
                st.error(f"No se pudo encontrar la hoja de trabajo para '{month_fortnight}'")
            else:
                st.success(f"Hoja de trabajo encontrada: '{sheet.title}'")

                # Get the data from the spreadsheet
                data = sheet.get_all_values()
                
                # Extract fortnight number from selection (e.g., "May - 1" -> "1")
                fortnight = month_fortnight.split(" - ")[1]
                
                # Parse spreadsheet data for the selected fortnight
                df_spreadsheet = parse_spreadsheet_data(data, fortnight)
                st.session_state.df_spreadsheet = df_spreadsheet
                
                if df_spreadsheet.empty:
                    st.warning(f"No se encontraron datos para la Quincena {fortnight} en la hoja de cálculo")
                else:
                    st.success(f"Se encontraron {len(df_spreadsheet)} vehículos en la Quincena {fortnight}")
        else:
            st.info("👆 Por favor, selecciona un mes y quincena para cargar los datos de la hoja de cálculo.")

    # RIGHT COLUMN: PDF upload
    with col_right:
        st.markdown("### 📄 Carga de PDF")
        
        pdf_path = st.file_uploader("Subir archivo PDF", type="pdf")

        if pdf_path:
            # Extract data from PDF
            df, before_taxes, iva, after_taxes = read_pdf(pdf_path)
            st.session_state.df_pdf = df
            st.session_state.pdf_totals = (before_taxes, iva, after_taxes)
            
            st.success(f"PDF procesado correctamente. Se encontraron {len(df)} artículos.")
        else:
            st.info("👆 Por favor, sube un archivo PDF para procesar.")

    # COMPARISON ANALYSIS SECTION (below both columns)
    st.markdown("---")
    
    # Only show comparison if both datasets are available
    if not st.session_state.df_spreadsheet.empty and not st.session_state.df_pdf.empty:
        df_comparison, total_pdf, total_diff, detailed_differences = compare_pdf_spreadsheet(
            st.session_state.df_pdf, st.session_state.df_spreadsheet
        )
        
        st.markdown("## 📊 Comparación por Matrícula")
        
        # Display summary metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(
                label="💰 Total PDF",
                value=f"€{total_pdf:.2f}"
            )
        with col2:
            total_spreadsheet = st.session_state.df_spreadsheet.groupby('Matricula')['Importe_Spreadsheet'].sum().sum()
            st.metric(
                label="📊 Total Hoja de Cálculo",
                value=f"€{total_spreadsheet:.2f}"
            )
        with col3:
            st.metric(
                label="⚖️ Diferencia",
                value=f"€{total_diff:.2f}",
                delta=f"{((total_diff/total_spreadsheet)*100):.1f}%" if total_spreadsheet != 0 else "N/A"
            )
        with col4:
            matches = len(df_comparison[abs(df_comparison['Diferencia']) < 0.01])
            total_vehicles = len(df_comparison)
            st.metric(
                label="✅ Coincidencias",
                value=f"{matches}/{total_vehicles}",
                delta=f"{(matches/total_vehicles*100):.1f}%" if total_vehicles > 0 else "0%"
            )
        
        # Display vehicle comparison dropdowns
        st.markdown("### 🚗 Análisis por Vehículo")
        
        # Sort vehicles by difference (largest differences first)
        df_sorted = df_comparison.sort_values('Diferencia', key=abs, ascending=False)
        
        for _, row in df_sorted.iterrows():
            matricula = row['Matricula']
            pdf_amount = row['Importe_PDF']
            spreadsheet_amount = row['Importe_Spreadsheet']
            difference = row['Diferencia']
            status = row['Estado']
            
            # Get PDF items for this vehicle
            pdf_items = st.session_state.df_pdf[st.session_state.df_pdf['Matricula'] == matricula].copy()
            
            # Create expander for each vehicle
            if abs(difference) < 0.01:
                # Matching vehicles - green indicator
                with st.expander(f"✅ {matricula} - €{pdf_amount:.2f} (Coincide)"):
                    st.success("Los importes coinciden perfectamente")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**PDF:** €{pdf_amount:.2f}")
                    with col2:
                        st.write(f"**Hoja de Cálculo:** €{spreadsheet_amount:.2f}")
                    
                    # Show PDF components
                    st.markdown("**📄 Componentes en PDF:**")
                    for _, item in pdf_items.iterrows():
                        st.write(f"• {item['Artículo']} - {item['Descripción']}: €{item['Total']:.2f}")
                        if item['Cantidad'] > 1 or item['Descuento'] > 0:
                            details = f"  Cantidad: {item['Cantidad']}"
                            if item['Precio'] > 0:
                                details += f" | Precio unitario: €{item['Precio']:.2f}"
                            if item['Descuento'] > 0:
                                details += f" | Descuento: {item['Descuento']:.1f}%"
                            st.caption(details)
            else:
                # Non-matching vehicles - red/orange indicator
                icon = "📈" if difference > 0 else "📉"
                with st.expander(f"{icon} {matricula} - Diferencia: €{difference:.2f}"):
                    if difference > 0:
                        st.error(f"El PDF tiene €{difference:.2f} más que la hoja de cálculo")
                    else:
                        st.warning(f"La hoja de cálculo tiene €{abs(difference):.2f} más que el PDF")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**PDF:** €{pdf_amount:.2f}")
                    with col2:
                        st.write(f"**Hoja de Cálculo:** €{spreadsheet_amount:.2f}")
                    
                    # Show PDF components
                    st.markdown("**📄 Componentes en PDF:**")
                    for _, item in pdf_items.iterrows():
                        st.write(f"• {item['Artículo']} - {item['Descripción']}: €{item['Total']:.2f}")
                        if item['Cantidad'] > 1 or item['Descuento'] > 0:
                            details = f"  Cantidad: {item['Cantidad']}"
                            if item['Precio'] > 0:
                                details += f" | Precio unitario: €{item['Precio']:.2f}"
                            if item['Descuento'] > 0:
                                details += f" | Descuento: {item['Descuento']:.1f}%"
                            st.caption(details)
                    
                    # Show detailed analysis if available
                    if matricula in detailed_differences:
                        details = detailed_differences[matricula]
                        
                        if details['potential_matches']:
                            st.markdown("**🎯 Análisis de Coincidencias:**")
                            for match in details['potential_matches']:
                                if match['type'] == 'exact_item_match':
                                    st.success(f"✅ Coincidencia exacta: {match['pdf_item']['articulo']} (€{match['pdf_item']['total']:.2f})")
                                elif match['type'] == 'combo_match':
                                    st.info(f"🔗 Combinación de artículos suma €{match['combo_total']:.2f}")
                                    for pdf_item in match['pdf_items']:
                                        st.write(f"  • {pdf_item['articulo']}: €{pdf_item['total']:.2f}")
                                elif match['type'] == 'closest_match':
                                    st.warning(f"📍 Más cercano: {match['pdf_item']['articulo']} (€{match['pdf_item']['total']:.2f}) - Diferencia: €{match['difference']:.2f}")
                        else:
                            st.error("❌ No se encontraron coincidencias potenciales")
        
    elif st.session_state.df_spreadsheet.empty and st.session_state.df_pdf.empty:
        st.info("📋 Selecciona un mes y sube un PDF para realizar el análisis de comparación.")
    elif st.session_state.df_spreadsheet.empty:
        st.warning("📅 Selecciona un mes para cargar los datos de la hoja de cálculo.")
    elif st.session_state.df_pdf.empty:
        st.warning("📄 Sube un archivo PDF para realizar la comparación.")

