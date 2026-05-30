using CsvHelper;
using System;
using System.Collections.Generic;
using System.Text;

namespace Energy_Truth.Shared.Providers
{
    public class UMeter : IEnergyProvider
    {
        public string Name => "UMeter";
        public bool IsCumulative => false;
        public string Delimiter => ",";
        public CsvMode CsvMode => CsvMode.RFC4180;
        public bool StripRowQuotes => true;
        List<string> IEnergyProvider.DateFormat => new List<string>() { "dd/MM/yyyy HH:mm" };
        public Dictionary<string, string> CsvMapping { get; } = new()
        {
            { nameof(EnergyImportDTO.Time), "time" },
            { nameof(EnergyImportDTO.ImportT1), "import_t1" },
            { nameof(EnergyImportDTO.ExportT1), "export_t1" },
        };

        public Dictionary<string, string> DisplayNames { get; } = new()
        {
            { nameof(EnergyImportDTO.Time), "From"  },
            { nameof(EnergyImportDTO.ImportT1), "Levering" },
            { nameof(EnergyImportDTO.ExportT1), "Teruglevering (kWh)" }
        };
    }
}
