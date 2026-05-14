using Moq;
using Energy_Truth_WEB_API.Services;
using Energy_Truth_WEB_API.Calculators;
using Energy_Truth.Shared;
using Energy_Truth.Shared.Providers;

namespace _04._Tests
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
                new EnergyImportDTO { Time = DateTime.Now.AddDays(-1), ImportT1 = 10, ImportT2 = 20, ExportT1 = 5, ExportT2 = 15, L1MaxW = 1000, L2MaxW = 2000, L3MaxW = 3000 },
                new EnergyImportDTO { Time = DateTime.Now, ImportT1 = 15, ImportT2 = 25, ExportT1 = 10, ExportT2 = 20, L1MaxW = 1100, L2MaxW = 2100, L3MaxW = 3100 }
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
                new EnergyImportDTO { Time = DateTime.Now.AddDays(-1), ImportT1 = 10, ImportT2 = 20, ExportT1 = 5, ExportT2 = 15, L1MaxW = 1000, L2MaxW = 2000, L3MaxW = 3000 },
                new EnergyImportDTO { Time = DateTime.Now, ImportT1 = 15, ImportT2 = 25, ExportT1 = 10, ExportT2 = 20, L1MaxW = 1100, L2MaxW = 2100, L3MaxW = 3100 }
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
                new EnergyImportDTO { Time = DateTime.Now.AddDays(-1), ImportT1 = 10, ImportT2 = 20, ExportT1 = 5, ExportT2 = 15, L1MaxW = 1000, L2MaxW = 2000, L3MaxW = 3000 },
            };

            //Act
            var result = service.CalculateEnergy(data, mockProvider.Object.Name);

            //Assert
            mockNonCumulativeCalculator.Verify(c => c.CalculateTotal(It.IsAny<List<EnergyImportDTO>>()), Times.Never);
            mockCumulativeCalculator.Verify(c => c.CalculateTotal(It.IsAny<List<EnergyImportDTO>>()), Times.Never);
        }
    }


}
