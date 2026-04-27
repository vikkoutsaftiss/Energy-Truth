using Energy_Truth.Shared;
using Energy_Truth.Shared.Providers;
using Energy_Truth_WEB_API.Calculators;

namespace Energy_Truth_WEB_API.Services
{
    public class EnergyCalculationService : IEnergyCalculationService
    {
        private readonly IEnumerable<IEnergyProvider> _energyProvider;
        private readonly ITotalCumulativeCalculator _totalCumulativeCalculator;
        private readonly ITotalNonCumulativeCalculator _totalNonCumulativeCalculator;

        public EnergyCalculationService(IEnumerable<IEnergyProvider> energyProvider, ITotalCumulativeCalculator totalCumulativeCalculator, ITotalNonCumulativeCalculator totalNonCumulativeCalculator)
        {
            _energyProvider = energyProvider;
            _totalCumulativeCalculator = totalCumulativeCalculator;
            _totalNonCumulativeCalculator = totalNonCumulativeCalculator;
        }

        public CalculationResultDTO CalculateEnergy(List<EnergyImportDTO> data, string providerName)
        {
            var provider = _energyProvider.FirstOrDefault(p => p.Name == providerName); // Hier wordt de provider opgezocht op basis van de naam die is meegegeven in de parameters.
            var result = new CalculationResultDTO();

            if (data == null || data.Count < 2) return result;

            // Sorteer op tijd (ervan uitgaande dat Time in EnergyImportDTO een DateTime is)
            var sorted = data.OrderBy(d => d.Time).ToList();

            if (sorted.Count < 2) return result;

            if (provider.IsCumulative)
            {
                // Als de provider cumulatief is, dan hoeven we alleen maar het verschil te nemen tussen de laatste en eerste waarde.
                result = _totalCumulativeCalculator.CalculateTotal(sorted);
            }
            else
            {
                // Als de provider niet cumulatief is, dan moeten we de waarden bij elkaar optellen.
                result = _totalNonCumulativeCalculator.CalculateTotal(sorted);
            }

            return result;
        }
    }    
}
