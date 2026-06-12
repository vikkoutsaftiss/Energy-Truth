using Energy_Truth.Shared.DTO_s;
using Energy_Truth_WEB_API.Controllers;
using Energy_Truth_WEB_API.Services.Battery;
using Energy_Truth_WEB_API.Services.Customer;
using Microsoft.AspNetCore.Mvc;
using Moq;
using System;
using System.Collections.Generic;
using System.Text;

namespace _04._Tests.ControllersTests
{
    public class BatteryControllerTest
    {
        [Fact]
        public async Task CheckIfGetBatteriesReturnsOkWhenServiceReturnsBatteries()
        {
            // Arrange
            var mockBatteryService = new Mock<IBatteryService>();
            var mockCustomerService = new Mock<ICustomerService>();
            mockBatteryService.Setup(s => s.GetBatteriesAsync()).ReturnsAsync(new List<BatteryDTO>());

            // Act
            var controller = new BatteryController(mockBatteryService.Object);
            var result = await controller.GetBatteries();

            // Assert
            Assert.IsType<OkObjectResult>(result);
        }

        [Fact]
        public async Task CheckIfGetBatteriesReturnsInternalServerErrorWhenServiceThrowsException()
        {
            // Arrange
            var mockBatteryService = new Mock<IBatteryService>();
            var mockCustomerService = new Mock<ICustomerService>();
            mockBatteryService.Setup(s => s.GetBatteriesAsync()).ThrowsAsync(new Exception());
            // Act
            var controller = new BatteryController(mockBatteryService.Object);
            var result = await controller.GetBatteries();
            // Assert
            var objectResult = Assert.IsType<ObjectResult>(result);
            Assert.Equal(500, objectResult.StatusCode);
            Assert.Equal("Er is iets fout gegaan bij het ophalen van de batterijen. Probeer het later opnieuw.", objectResult.Value);
        }

        [Fact]
        public async Task CheckIfUpdateBatteryReturnsNoContentWhenUpdateSucceeds()
        {
            // Arrange
            var mockBatteryService = new Mock<IBatteryService>();
            var mockCustomerService = new Mock<ICustomerService>();
            int batteryId = 1;
            var batteryDto = new BatteryDTO();
            mockBatteryService.Setup(s => s.UpdateBatteryAsync(batteryId, batteryDto)).ReturnsAsync(true);
            // Act
            var controller = new BatteryController(mockBatteryService.Object);
            var result = await controller.UpdateBattery(batteryId, batteryDto);
            // Assert
            Assert.IsType<NoContentResult>(result);
        }

        [Fact]
        public async Task CheckIfUpdateBatteryReturnsNotFoundWhenBatteryDoesNotExist()
        {
            // Arrange
            var mockBatteryService = new Mock<IBatteryService>();
            var mockCustomerService = new Mock<ICustomerService>();
            int batteryId = 1;
            var batteryDto = new BatteryDTO();
            mockBatteryService.Setup(s => s.UpdateBatteryAsync(batteryId, batteryDto)).ReturnsAsync(false);
            // Act
            var controller = new BatteryController(mockBatteryService.Object);
            var result = await controller.UpdateBattery(batteryId, batteryDto);
            // Assert
            Assert.IsType<NotFoundResult>(result);
        }

        [Fact]
        public async Task CheckIfUpdateBatteryReturnsInternalServerErrorWhenServiceThrowsException()
        {
            // Arrange
            var mockBatteryService = new Mock<IBatteryService>();
            var mockCustomerService = new Mock<ICustomerService>();
            int batteryId = 1;
            var batteryDto = new BatteryDTO();
            mockBatteryService.Setup(s => s.UpdateBatteryAsync(batteryId, batteryDto)).ThrowsAsync(new Exception());
            // Act
            var controller = new BatteryController(mockBatteryService.Object);
            var result = await controller.UpdateBattery(batteryId, batteryDto);
            // Assert
            var objectResult = Assert.IsType<ObjectResult>(result);
            Assert.Equal(500, objectResult.StatusCode);
            Assert.Equal("Er is iets fout gegaan bij het bijwerken van de batterij. Probeer het later opnieuw.", objectResult.Value);
        }

        [Fact]
        public async Task CheckIfCreateBatteryReturnsOkWhenValidBatteryHasBeenAdded()
        {
            // Arrange
            var mockBatteryService = new Mock<IBatteryService>();
            var mockCustomerService = new Mock<ICustomerService>();
            var batteryDto = new BatteryDTO();
            mockBatteryService.Setup(s => s.CreateBatteryAsync(batteryDto)).ReturnsAsync(batteryDto);
            // Act
            var controller = new BatteryController(mockBatteryService.Object);
            var result = await controller.CreateBattery(batteryDto);
            // Assert
            Assert.IsType<OkObjectResult>(result);
        }

        [Fact]
        public async Task CheckIfCreateBatteryReturnsBadRequestWhenResultIsNull()
        {
            // Arrange
            var mockBatteryService = new Mock<IBatteryService>();
            var mockCustomerService = new Mock<ICustomerService>();
            var batteryDto = new BatteryDTO();
            mockBatteryService.Setup(s => s.CreateBatteryAsync(batteryDto)).ReturnsAsync((BatteryDTO)null);
            // Act
            var controller = new BatteryController(mockBatteryService.Object);
            var result = await controller.CreateBattery(batteryDto);
            // Assert
            var badRequestResult = Assert.IsType<BadRequestObjectResult>(result);
        }

        [Fact]
        public async Task CheckIfCreateBatteryReturnsInternalServerErrorWhenServiceThrowsException()
        {
            // Arrange
            var mockBatteryService = new Mock<IBatteryService>();
            var mockCustomerService = new Mock<ICustomerService>();
            var batteryDto = new BatteryDTO();
            mockBatteryService.Setup(s => s.CreateBatteryAsync(batteryDto)).ThrowsAsync(new Exception());
            // Act
            var controller = new BatteryController(mockBatteryService.Object);
            var result = await controller.CreateBattery(batteryDto);
            // Assert
            var objectResult = Assert.IsType<ObjectResult>(result);
            Assert.Equal(500, objectResult.StatusCode);
            Assert.Equal("Er is iets fout gegaan bij het aanmaken van de batterij. Probeer het later opnieuw.", objectResult.Value);
        }
    }
}