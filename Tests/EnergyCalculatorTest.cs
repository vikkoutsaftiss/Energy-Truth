using Moq;
using Energy_Truth_WEB_API.Services;
using Energy_Truth.Shared;

namespace _04._Tests
{
    public class EnergyCalculatorTest
    {
        [Fact]
        public void CheckIfResultIsCalculatedCorrectly()
        {
            //Arrange
            var service = new EnergyCalculationService();
            var data = new List<EnergyImportDTO>
            {
                new EnergyImportDTO { Time = DateTime.Now.AddDays(-1), ImportT1 = 10, ImportT2 = 20, ExportT1 = 5, ExportT2 = 15, L1MaxW = 1000, L2MaxW = 2000, L3MaxW = 3000 },
                new EnergyImportDTO { Time = DateTime.Now, ImportT1 = 15, ImportT2 = 25, ExportT1 = 10, ExportT2 = 20, L1MaxW = 1100, L2MaxW = 2100, L3MaxW = 3100 }
            };

            //Act
            var result = service.CalculateEnergy(data);

            //Assert
            Assert.Equal(10, result.TotalExportKwh);
            Assert.Equal(10, result.TotalImportKwh);
        }
    }
}
