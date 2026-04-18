namespace Energy_Truth_WEB_API.Calculators
{
    public class TotalExportCalculator : ITotalEnergyCalculator
    {
        public double CalculateTotalImport(double exportT1, double exportT2)
        {
            double totalExport = exportT1 + exportT2;
            return totalExport;
        }
    
    }
}
