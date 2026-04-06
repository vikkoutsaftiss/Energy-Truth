namespace Energy_Truth_WEB_API.Calculators
{
    public class TotalImportCalculator : ITotalEnergyCalculator
    {
        public double CalculateTotalImport(double importT1, double importT2)
        {
            double totalUsage = importT1 + importT2;

            return totalUsage;
        }
    }
}
