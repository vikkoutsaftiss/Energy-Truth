using _04._Tests.Builders;
using Energy_Truth.Shared.DTO_s;
using Energy_Truth.Shared.Repositories;
using Energy_Truth_WEB_API.Services.Building;
using Microsoft.AspNetCore.Mvc;
using Moq;
using System;
using System.Collections.Generic;
using System.Text;

namespace _04._Tests.ServicesTests
{
    public class BuildingServiceTest
    {
        [Fact]
        public async Task CheckIfCreateBuildingSucceedsWithStandardBuilding()
        {
            // Arrange
            var mockBuildingRepository = new Mock<IBuildingRepository>();
            var expectedBuilding = new BuildingDTOBuilder().Build();
            mockBuildingRepository.Setup(r => r.CreateBuildingAsync(It.IsAny<BuildingDTO>())).ReturnsAsync(1);
            var buildingService = new BuildingService(mockBuildingRepository.Object);
            var buildingDTO = new BuildingDTOBuilder().Build();
            // Act
            var result = await buildingService.CreateBuildingAsync(buildingDTO);
            // Assert
            Assert.Equal(1, result);
        }

        [Fact]
        public async Task CheckIfCreateBuildingThrowsExceptionWhenBuildingExists()
        {
            // Arrange
            var mockBuildingRepository = new Mock<IBuildingRepository>();
            var buildingDTO = new BuildingDTOBuilder().Build();

            mockBuildingRepository.Setup(r => r.GetBuildingIdByPostalCodeAndCustomerIdAsync(
                    It.IsAny<string>(), It.IsAny<int>()))
                .ReturnsAsync(1);

            var buildingService = new BuildingService(mockBuildingRepository.Object);

            // Act & Assert
            var exception = await Assert.ThrowsAsync<InvalidOperationException>(
                () => buildingService.CreateBuildingAsync(buildingDTO)
            );

            Assert.Equal("Dit gebouw bestaat al in jouw profiel.", exception.Message);
        }
    }
}
