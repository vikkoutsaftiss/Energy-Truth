using CsvHelper.Configuration.Attributes;
using System.ComponentModel.DataAnnotations;

namespace Energy_Truth.Shared
{
    public class EnergyImportDTO
    {
        [Name("time")]
        public DateTime Time { get; set; }

        [Name("Import T1 kWh")]
        public double? ImportT1 { get; set; }

        [Name("Import T2 kWh")]
        public double? ImportT2 { get; set; }

        [Name("Export T1 kWh")]
        public double? ExportT1 { get; set; }

        [Name("Export T2 kWh")]
        public double? ExportT2 { get; set; }

        [Name("L1 max W")]
        public int? L1MaxW { get; set; }

        [Name("L2 max W")]
        public int? L2MaxW { get; set; }

        [Name("L3 max W")]
        public int? L3MaxW { get; set; }
    }
}
