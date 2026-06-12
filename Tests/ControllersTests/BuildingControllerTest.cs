using _04._Tests.Builders;
using Energy_Truth.Shared.DTO_s;
using Energy_Truth_WEB_API.Controllers;
using Energy_Truth_WEB_API.Services.Building;
using Microsoft.AspNetCore.Mvc;
using Moq;
using System;
using System.Collections.Generic;
using System.Text;

namespace _04._Tests.ControllersTests
{
    public class BuildingControllerTest
    {
        [Fact]
        public async Task CheckIfCreateBuildingSucceedsWithStandardBuilding()
        {
            // Arrange
            var mockBuildingService = new Mock<IBuildingService>();
            mockBuildingService
                .Setup(s => s.CreateBuildingAsync(It.IsAny<BuildingDTO>()))
                .ReturnsAsync(1);
            var controller = new BuildingController(mockBuildingService.Object);
            var buildingDTO = new BuildingDTOBuilder().Build();
            // Act
            var result = await controller.CreateBuilding(buildingDTO);
            // Assert
            Assert.IsType<OkObjectResult>(result);
        }

        [Fact]
        public async Task CheckIfCreateBuildingReturnsBadRequestWhenCustomerIDIs0()
        {
            // Arrange
            var mockBuildingService = new Mock<IBuildingService>();
            var controller = new BuildingController(mockBuildingService.Object);
            var buildingDTO = new BuildingDTOBuilder().WithCustomerId(0).Build();
            // Act
            var result = await controller.CreateBuilding(buildingDTO);
            // Assert
            var badRequestResult = Assert.IsType<BadRequestObjectResult>(result);
            Assert.Equal("Ongeldige klant ID.", badRequestResult.Value);

        }

        [Fact]
        public async Task CheckIfCreateBuildingFailsWithPostalCodeNull()
        {
            // Arrange
            var mockBuildingService = new Mock<IBuildingService>();
            var controller = new BuildingController(mockBuildingService.Object);
            var buildingDTO = new BuildingDTOBuilder().WithPostalCode(null).Build();
            // Act
            var result = await controller.CreateBuilding(buildingDTO);
            // Assert
            var badRequestResult = Assert.IsType<BadRequestObjectResult>(result);
            Assert.Equal("Postcode is verplicht.", badRequestResult.Value);
        }

        [Fact]
        public async Task CheckIfCreateBuildingFailsWithBuildingNull()
        {
            // Arrange
            var mockBuildingService = new Mock<IBuildingService>();
            var controller = new BuildingController(mockBuildingService.Object);
            BuildingDTO buildingDTO = null;
            // Act
            var result = await controller.CreateBuilding(buildingDTO);
            // Assert
            var badRequestResult = Assert.IsType<BadRequestObjectResult>(result);
            Assert.Equal("Ongeldige gebouwgegevens.", badRequestResult.Value);
        }

        [Fact]
        public async Task CheckIfCreateBuildingReturnsInternalServerErrorWhenServiceThrowsException()
        {
            // Arrange
            var mockBuildingService = new Mock<IBuildingService>();
            mockBuildingService
            .Setup(s => s.CreateBuildingAsync(It.IsAny<BuildingDTO>()))
                .ThrowsAsync(new Exception("Test exception"));
            var controller = new BuildingController(mockBuildingService.Object);
            var buildingDTO = new BuildingDTOBuilder().Build();
            // Act
            var result = await controller.CreateBuilding(buildingDTO);
            // Assert
            var objectResult = Assert.IsType<ObjectResult>(result);
            Assert.Equal(500, objectResult.StatusCode);
            Assert.Equal("Er is een fout opgetreden bij het aanmaken van het gebouw: Test exception", objectResult.Value);

        }

        [Fact]
        public async Task CheckIfGetBuildingByCustomerIdReturnsBadRequestWhenCustomerIDIs0()
        {
            // Arrange
            var mockBuildingService = new Mock<IBuildingService>();
            var controller = new BuildingController(mockBuildingService.Object);
            int customerId = 0;
            // Act
            var result = await controller.GetBuildingByCustomerId(customerId);
            // Assert
            var badRequestResult = Assert.IsType<BadRequestObjectResult>(result);
            Assert.Equal("Ongeldige klant ID.", badRequestResult.Value);
        }

        [Fact]
        public async Task CheckIfGetBuildingByCustomerIdReturnsInternalServerErrorWhenServiceThrowsException()
        {
            // Arrange
            var mockBuildingService = new Mock<IBuildingService>();
            int customerId = 1;
            mockBuildingService
                .Setup(s => s.GetBuildingsByCustomerIdAsync(customerId))
                .ThrowsAsync(new Exception("Test exception"));
            var controller = new BuildingController(mockBuildingService.Object);
            // Act
            var result = await controller.GetBuildingByCustomerId(customerId);
            // Assert
            var objectResult = Assert.IsType<ObjectResult>(result);
            Assert.Equal(500, objectResult.StatusCode);
            Assert.Equal("Er is een fout opgetreden bij het ophalen van het gebouw: Test exception", objectResult.Value);

        }

        [Fact]
        public async Task CheckIfGetBuildingByCustomerIdReturnsNotFoundWhenNoBuildingsFound()
        {
            // Arrange
            var mockBuildingService = new Mock<IBuildingService>();
            int customerId = 1;
            mockBuildingService
                .Setup(s => s.GetBuildingsByCustomerIdAsync(customerId))
                .ReturnsAsync((List<BuildingDTO>)null);
            var controller = new BuildingController(mockBuildingService.Object);
            // Act
            var result = await controller.GetBuildingByCustomerId(customerId);
            // Assert
            var notFoundResult = Assert.IsType<NotFoundObjectResult>(result);
            Assert.Equal("Geen gebouw gevonden voor deze klant en postcode.", notFoundResult.Value);

        }

        [Fact]
        public async Task CheckIfGetBuildingByCustomerIdReturnsOkWhenBuildingsFound()
        {
            // Arrange
            var mockBuildingService = new Mock<IBuildingService>();
            int customerId = 1;
            var buildings = new List<BuildingDTO>
            {
                new BuildingDTOBuilder().Build(),
                new BuildingDTOBuilder().WithPostalCode("1234KK").Build()
            };
            mockBuildingService
                .Setup(s => s.GetBuildingsByCustomerIdAsync(customerId))
                .ReturnsAsync(buildings);
            var controller = new BuildingController(mockBuildingService.Object);
            // Act
            var result = await controller.GetBuildingByCustomerId(customerId);
            // Assert
            var okResult = Assert.IsType<OkObjectResult>(result);
            var returnedBuildings = Assert.IsType<List<BuildingDTO>>(okResult.Value);
            Assert.Equal(2, returnedBuildings.Count);
        }
    }
}
