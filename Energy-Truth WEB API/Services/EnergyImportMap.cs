namespace Energy_Truth_WEB_API;

using CsvHelper.Configuration;
using Energy_Truth.Shared;

public sealed class EnergyImportMap : ClassMap<EnergyImportDTO>
{
    public EnergyImportMap()
    {
        // Hier vertel je CsvHelper welke kolomnaam bij welke property hoort
        Map(m => m.Time).Name("time").TypeConverterOption.Format("yyyy-MM-dd HH:mm", "M/d/yyyy H:mm", "dd-MM-yyyy HH:mm"); 
        Map(m => m.ImportT1).Name("Import T1 kWh");
        Map(m => m.ImportT2).Name("Import T2 kWh");
        Map(m => m.ExportT1).Name("Export T1 kWh");
        Map(m => m.ExportT2).Name("Export T2 kWh");
        Map(m => m.L1MaxW).Name("L1 max W");
        Map(m => m.L2MaxW).Name("L2 max W");
        Map(m => m.L3MaxW).Name("L3 max W");
        // 'Time' hoeft niet als de kolom in de CSV ook 'Time' heet
    }
}
