using CsvHelper;
using CsvHelper.Configuration.Attributes;
using System;
using System.Collections.Generic;
using System.Text;
using System.Text.Json.Nodes;

namespace Energy_Truth.Shared.Providers
{
    public class HomeWizard : IEnergyProvider
    {
        public string Name => "HomeWizard";
        public bool IsCumulative => true;
        public CsvMode CsvMode => CsvMode.Escape;
        public string Delimiter => ",";
        public bool StripRowQuotes => false;
        public List<string> DateFormat => new() { "yyyy-MM-dd HH:mm", "M/d/yyyy H:mm" };

        public Dictionary<string, string> CsvMapping { get; } = new()
        {
            { nameof(EnergyImportDTO.Time), "time" },
            { nameof(EnergyImportDTO.ImportT1), "Import T1 kWh" },
            { nameof(EnergyImportDTO.ImportT2), "Import T2 kWh" },
            { nameof(EnergyImportDTO.ExportT1), "Export T1 kWh" },
            { nameof(EnergyImportDTO.ExportT2), "Export T2 kWh" },
            { nameof(EnergyImportDTO.L1MaxW), "L1 Max W" },
            { nameof(EnergyImportDTO.L2MaxW), "L2 Max W" },
            { nameof(EnergyImportDTO.L3MaxW), "L3 Max W" }
        };

        public Dictionary<string, string> DisplayNames { get; } = new()
        {
            { nameof(EnergyImportDTO.Time), "Tijd" },
            { nameof(EnergyImportDTO.ImportT1), "Import kWh normaal tarief" },
            { nameof(EnergyImportDTO.ImportT2), "Import kWh dal tarief" },
            { nameof(EnergyImportDTO.ExportT1), "Export kWh normaal tarief" },
            { nameof(EnergyImportDTO.ExportT2), "Export kWh dal tarief" },
            { nameof(EnergyImportDTO.L1MaxW), "Fase 1 maximale belasting" },
            { nameof(EnergyImportDTO.L2MaxW), "Fase 2 maximale belasting" },
            { nameof(EnergyImportDTO.L3MaxW), "Fase 3 maximale belasting" }
        };

    }
}
