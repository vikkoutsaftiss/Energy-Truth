using System.Text.Json.Serialization;

namespace Energy_Truth.Shared
{
    public class CalculationResultDTO
    {
        public double TotalImportKwh { get; set; }
        public double TotalExportKwh { get; set; }
    }
}
