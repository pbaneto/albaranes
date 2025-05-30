import pdfplumber
import pandas as pd
import streamlit as st


def format_main_table(table): 
    # Header is the first line that contains "Artículo"
    for idx, line in enumerate(table):
        if "Artículo" in line:
            header_idx = idx
            break

    result = []
    matricula = ''
    fecha = None
    
    # When found line with albaran we update matricula and fecha
    for line in table[header_idx+1:]:           
        # if all elements in line are empty, skip
        if all(item == "" for item in line):
            continue
            
        if any('ABONO' in item for item in line):
            continue
        
        # Albaran will be part of a string like "ALBARAN 1234567890", double check if albaran is present
        albaran_idx = [idx for idx, element in enumerate(line) if element.startswith("ALBARAN")]
        matricula_idx = [idx for idx, element in enumerate(line) if element.startswith("A:")]
        if len(albaran_idx) > 0 and len(matricula_idx) > 0:
            albaran_line = line[albaran_idx[0]]
            fecha = albaran_line.split(" ")[-1]
            matricula = line[matricula_idx[0]].split(":")[1]
            continue
        
        articulo = line[0]
        descripcion = line[1]
        cantidad = line[2]
        precio = line[3].replace(',', '.')
        descuento = line[4]
        total = line[5].replace(',', '.')

        result.append({
            'Matrícula': matricula,
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
    '''
    Numbers are in this format: '1.399,5'
    The output should be 1399.5
    '''
    item = item.replace('.', '')
    item = item.replace(',', '.')
    return float(item)


def find_total_invoice(table_total):
    # Bruto e IVA
    item = table_total[1][-3]
    bruto_pdf = convert_str_to_float(item.split(" ")[0])
    iva_pdf = convert_str_to_float(item.split(" ")[1])

    # Neto
    neto_pdf = table_total[2][-1]
    neto_pdf = convert_str_to_float(neto_pdf)

    return bruto_pdf, iva_pdf, neto_pdf



def read_pdf(pdf_path):
    table_settings = {
        'vertical_strategy': 'lines',
        'horizontal_strategy': 'text',
        'intersection_tolerance': 5
    }

    with pdfplumber.open(pdf_path) as pdf:

        # Extract text from each page using crop
        all_items = []
        for page in pdf.pages:

            table = page.extract_table(table_settings=table_settings)
            items = format_main_table(table)

            print(f"Page {page.page_number} has {len(items)} items")

            all_items.extend(items)

            # Just look for the total on the last page
            if page.page_number == len(pdf.pages):       
                tables = page.extract_tables(table_settings=table_settings)
                table_total = tables[-1]
                before_taxes_pdf, iva_pdf, after_taxes_pdf = find_total_invoice(table_total)


    df = pd.DataFrame(all_items)
    # Convert cantidad, precio, descuento, total to float
    df['Cantidad'] = df['Cantidad'].astype(float)
    df['Precio'] = df['Precio'].astype(float)
    df['Descuento'] = df['Descuento'].astype(float)
    df['Total'] = df['Total'].astype(float)

    before_taxes = df['Total'].sum()

    # Calculate iva and neto
    iva = before_taxes * 0.21
    after_taxes = before_taxes + iva

    # Compare the totals
    print(f"Antes de impuestos: {before_taxes_pdf}, IVA: {iva_pdf}, Despues de impuestos: {after_taxes_pdf} reading the pdf")
    print(f"Antes de impuestos: {before_taxes}, IVA: {iva}, Despues de impuestos: {after_taxes} adding all items")

    # Compare just the number with two decimals
    if round(before_taxes_pdf, 2) == round(before_taxes, 2) and round(iva_pdf, 2) == round(iva, 2) and round(after_taxes_pdf, 2) == round(after_taxes, 2):
        print("Totals match")
        return df, before_taxes, iva, after_taxes
    else:
        print("Totals do not match")
        return None, None, None, None



st.set_page_config(layout="wide")  
st.title("💸 Facturing")

# TODO: Get items data from the spreadsheet. 

# - Add a month selector? to take the correct sheet from the spreadsheet

# Show some graphics for the spreadsheet
# - what car has the most items?
# - what car has the most total?
# - what car has the highest benefit?
# - graph with benefit per car

pdf_path = st.file_uploader("Upload a PDF file", type="pdf")

if pdf_path:

    df, before_taxes, iva, after_taxes = read_pdf(pdf_path)
    
    # For each unique matricula, sum the total
    df_grouped = df.groupby('Matrícula')['Total'].sum().reset_index()
    df_grouped = df_grouped.sort_values(by='Total', ascending=False)

    # Show the dataframe without index
    st.dataframe(df_grouped, width=300, hide_index=True)

    # TODO: Check if each car (matricula) has spent the same amount of money in the df_grouped compared to the df
    # TODO:Table with matricula, total in df, total in df_grouped, difference







    st.markdown("---")  # Add a separator line

    # Display df with all the items
    st.dataframe(df, use_container_width=True, width=1500, hide_index=True)

    # Display the totals
    st.markdown("---")  # Add a separator line
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(
            label="💰 Antes de impuestos",
            value=f"€{before_taxes:.2f}"
        )
    with col2:
        st.metric(
            label="📊 IVA (21%)",
            value=f"€{iva:.2f}"
        )
    with col3:
        st.metric(
            label="💸 Total",
            value=f"€{after_taxes:.2f}"
        )

