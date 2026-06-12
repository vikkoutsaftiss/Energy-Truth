using Moq;
using Energy_Truth_WEB_API.Services;
using Energy_Truth_WEB_API.Calculators;
using Energy_Truth.Shared;
using Energy_Truth.Shared.Providers;

namespace _04._Tests.ServicesTests
{
    public class EnergyCalculationServiceTest
    {
        [Fact]
        public void CheckIfServiceChoosesRightCalculatorWhenProviderIsHomeWizard()
        {
            //Arrange
            var mockProvider = new Mock<IEnergyProvider>();
            mockProvider.Setup(p => p.Name).Returns("HomeWizard");
            mockProvider.Setup(p => p.IsCumulative).Returns(true);
            var mockCumulativeCalculator = new Mock<ITotalCumulativeCalculator>();            
            var mockNonCumulativeCalculator = new Mock<ITotalNonCumulativeCalculator>();
            IEnumerable<IEnergyProvider> providers = new List<IEnergyProvider> { mockProvider.Object };

            var service = new EnergyCalculationService(providers, mockCumulativeCalculator.Object, mockNonCumulativeCalculator.Object);

            var data = new List<EnergyImportDTO>
            {
                new EnergyImportDTOBuilder().Build(),
                new EnergyImportDTOBuilder().Build()
            };

            //Act
            var result = service.CalculateEnergy(data, mockProvider.Object.Name);

            //Assert
            mockCumulativeCalculator.Verify(c => c.CalculateTotal(It.IsAny<List<EnergyImportDTO>>()), Times.Once);
        }

        [Fact]
        public void CheckIfServiceChoosesRightCalculatorWhenProviderIsUMeter()
        {
            //Arrange
            var mockProvider = new Mock<IEnergyProvider>();
            mockProvider.Setup(p => p.Name).Returns("UMeter");
            mockProvider.Setup(p => p.IsCumulative).Returns(false);
            var mockCumulativeCalculator = new Mock<ITotalCumulativeCalculator>();
            var mockNonCumulativeCalculator = new Mock<ITotalNonCumulativeCalculator>();
            IEnumerable<IEnergyProvider> providers = new List<IEnergyProvider> { mockProvider.Object };

            var service = new EnergyCalculationService(providers, mockCumulativeCalculator.Object, mockNonCumulativeCalculator.Object);
            var data = new List<EnergyImportDTO>
            {
                new EnergyImportDTOBuilder().Build(),
                new EnergyImportDTOBuilder().Build()
            };

            //Act
            var result = service.CalculateEnergy(data, mockProvider.Object.Name);

            //Assert
            mockNonCumulativeCalculator.Verify(c => c.CalculateTotal(It.IsAny<List<EnergyImportDTO>>()), Times.Once);
        }

        [Fact]
        public void CheckIfServiceReturnsWhenDataSmallerThan2()
        {
            //Arrange
            var mockProvider = new Mock<IEnergyProvider>();
            mockProvider.Setup(p => p.Name).Returns("UMeter");
            mockProvider.Setup(p => p.IsCumulative).Returns(false);
            var mockCumulativeCalculator = new Mock<ITotalCumulativeCalculator>();
            var mockNonCumulativeCalculator = new Mock<ITotalNonCumulativeCalculator>();
            IEnumerable<IEnergyProvider> providers = new List<IEnergyProvider> { mockProvider.Object };

            var service = new EnergyCalculationService(providers, mockCumulativeCalculator.Object, mockNonCumulativeCalculator.Object);
            var data = new List<EnergyImportDTO>
            {
                new EnergyImportDTOBuilder().Build(),
            };

            //Act
            var result = service.CalculateEnergy(data, mockProvider.Object.Name);

            //Assert
            mockNonCumulativeCalculator.Verify(c => c.CalculateTotal(It.IsAny<List<EnergyImportDTO>>()), Times.Never);
            mockCumulativeCalculator.Verify(c => c.CalculateTotal(It.IsAny<List<EnergyImportDTO>>()), Times.Never);
        }
    }


}
