#!/usr/bin/env python3
"""
Test script to demonstrate the enhanced compare_pdf_spreadsheet function
with detailed item-level differences and matching capabilities.
"""

import pandas as pd
from main import compare_pdf_spreadsheet

def test_detailed_differences():
    """Test the enhanced compare_pdf_spreadsheet function with sample data."""
    
    print("🧪 Testing Enhanced compare_pdf_spreadsheet Function")
    print("=" * 60)
    
    # Create sample PDF data with multiple scenarios
    df_pdf = pd.DataFrame({
        'Matricula': ['ABC123', 'ABC123', 'XYZ789', 'DEF456', 'DEF456', 'GHI999'],
        'Fecha': ['20250101', '20250101', '20250102', '20250103', '20250103', '20250104'],
        'Artículo': ['ART001', 'ART002', 'ART003', 'ART004', 'ART005', 'ART006'],
        'Descripción': ['Fuel', 'Maintenance', 'Repair', 'Fuel', 'Tires', 'Service'],
        'Cantidad': [1.0, 1.0, 1.0, 1.0, 2.0, 1.0],
        'Precio': [100.0, 100.0, 180.0, 75.0, 50.0, 120.0],
        'Descuento': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        'Total': [100.0, 100.0, 180.0, 75.0, 100.0, 120.0]
    })
    
    # Create sample spreadsheet data
    # ABC123: Exact match (200.0 = 100.0 + 100.0)
    # XYZ789: Close match (180.0 vs 180.0)
    # DEF456: Partial match (175.0 vs 75.0 + 100.0)
    # GHI999: Only in PDF (120.0)
    # JKL000: Only in spreadsheet (300.0)
    df_spreadsheet = pd.DataFrame({
        'Matricula': ['ABC123', 'XYZ789', 'DEF456', 'JKL000'],
        'Importe_Spreadsheet': [200.0, 180.0, 175.0, 300.0]
    })
    
    print("📄 Sample PDF Data:")
    print(df_pdf.to_string(index=False))
    print("\n📊 Sample Spreadsheet Data:")
    print(df_spreadsheet.to_string(index=False))
    
    # Test the function
    df_comparison, total_pdf, total_diff, detailed_differences = compare_pdf_spreadsheet(df_pdf, df_spreadsheet)
    
    print("\n🔍 Comparison Results:")
    print(df_comparison.to_string(index=False))
    
    print(f"\n💰 Summary:")
    print(f"Total PDF: €{total_pdf:.2f}")
    print(f"Total Spreadsheet: €{df_spreadsheet['Importe_Spreadsheet'].sum():.2f}")
    print(f"Total Difference: €{total_diff:.2f}")
    
    print(f"\n🚗 Detailed Differences for {len(detailed_differences)} vehicles:")
    
    for matricula, details in detailed_differences.items():
        print(f"\n--- {matricula} ---")
        print(f"PDF Total: €{details['pdf_total']:.2f}")
        print(f"Spreadsheet Total: €{details['spreadsheet_total']:.2f}")
        print(f"Difference: €{details['difference']:.2f}")
        
        print(f"\nPDF Items ({len(details['pdf_items'])}):")
        for item in details['pdf_items']:
            print(f"  • {item['articulo']}: {item['descripcion']} - €{item['total']:.2f}")
        
        print(f"\nPotential Matches ({len(details['potential_matches'])}):")
        for match in details['potential_matches']:
            if match['type'] == 'exact_item_match':
                print(f"  ✅ EXACT: {match['pdf_item']['articulo']} (€{match['pdf_item']['total']:.2f})")
            elif match['type'] == 'combo_match':
                items = " + ".join([f"{item['articulo']} (€{item['total']:.2f})" for item in match['pdf_items']])
                print(f"  🔗 COMBO: {items} = €{match['combo_total']:.2f}")
            elif match['type'] == 'closest_match':
                print(f"  📍 CLOSEST: {match['pdf_item']['articulo']} (€{match['pdf_item']['total']:.2f}, diff: €{match['difference']:.2f})")

if __name__ == "__main__":
    test_detailed_differences() 