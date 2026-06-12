using Moq;
using Energy_Truth_WEB_API.Services;
using Energy_Truth.Shared.Repositories;
using Energy_Truth.Shared.DTO_s;
using _04._Tests.Builders;
using Energy_Truth_WEB_API.Services.Battery;


namespace _04._Tests.ServicesTests
{
    public class BatteryServiceTest
    {
        [Fact]
        public async Task CheckIfBatterryServiceReturnsBatteryAfterSuccessfullyCreated()
        {
            // Arrange
            var mockBatteryRepository = new Mock<IBatteryRepository>();
            var expectedBattery = new BatteryDTOBuilder().Build();
            mockBatteryRepository.Setup(r => r.GetBatteriesAsync()).ReturnsAsync(new List<BatteryDTO> { expectedBattery });
            var batteryService = new BatteryService(mockBatteryRepository.Object);
            // Act
            var batteries = await batteryService.GetBatteriesAsync();
            // Assert
            Assert.NotNull(batteries);
            Assert.Single(batteries);
            Assert.Equal(expectedBattery.Id, batteries[0].Id);
        }

        [Fact]
        public async Task CheckIfBatteryServiceReturnsBatteryAfterSuccessfullyCreated()
        {
            // Arrange
            var mockBatteryRepository = new Mock<IBatteryRepository>();
            var expectedBattery = new BatteryDTOBuilder().Build();
            mockBatteryRepository.Setup(r => r.GetBatteriesAsync()).ReturnsAsync(new List<BatteryDTO> { expectedBattery });
            var batteryService = new BatteryService(mockBatteryRepository.Object);
            // Act
            var batteries = await batteryService.GetBatteriesAsync();
            // Assert
            Assert.NotNull(batteries);
            Assert.Single(batteries);
            Assert.Equal(expectedBattery.Id, batteries[0].Id);
        }
    }
}
