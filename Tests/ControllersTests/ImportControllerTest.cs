using Energy_Truth.Shared;
using Energy_Truth_WEB_API.Controllers;
using Energy_Truth.Shared.DTO_s;
using Energy_Truth_WEB_API.Services;
using Energy_Truth_WEB_API.Services.Import;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using Moq;
using Energy_Truth_WEB_API.Services.DateFilter;
using Energy_Truth_WEB_API.Calculators;
using Energy_Truth.Shared.Repositories;


namespace _04._Tests.ControllersTests
{
    public class ImportControllerTest
    {
        [Fact]
        public async Task CheckIfBadRequestsAreTriggeredWhenFileIsNull()
        {
            // Arrange
            var mockCalculationService = new Mock<IEnergyCalculationService>();
            var mockImportService = new Mock<IImportService>();
            var mockDateFilterService = new Mock<IDateFilterService>();
            var mockImportCalculator = new Mock<IImportCalculator>();
            var mockUsageDataRepository = new Mock<IUsageDataRepository>();
            var controller = new ImportController(mockImportService.Object, mockCalculationService.Object, mockDateFilterService.Object, mockImportCalculator.Object, mockUsageDataRepository.Object);
            IFormFile file = null;
            string mapping = "{\"Time\":\"Time\",\"ImportT1\":\"ImportT1\",\"ImportT2\":\"ImportT2\",\"ExportT1\":\"ExportT1\",\"ExportT2\":\"ExportT2\",\"L1MaxW\":\"L1MaxW\",\"L2MaxW\":\"L2MaxW\",\"L3MaxW\":\"L3MaxW\"}";
            string provider = "TestProvider";
            int buildingId = 1;

            // Act
            var result = await controller.UploadCsv(file, mapping, provider, buildingId);

            // Assert
            Assert.IsType<BadRequestObjectResult>(result);
            Assert.Equal("Geen bestand ontvangen.", ((BadRequestObjectResult)result).Value);
        }

        [Fact]
        public async Task CheckIfBadRequestsAreTriggeredWhenMappingIsInvalid()
        {
            // Arrange
            var mockCalculationService = new Mock<IEnergyCalculationService>();
            var mockImportService = new Mock<IImportService>();
            var mockDateFilterService = new Mock<IDateFilterService>();
            var mockImportCalculator = new Mock<IImportCalculator>();
            var mockUsageDataRepository = new Mock<IUsageDataRepository>();
            var controller = new ImportController(mockImportService.Object, mockCalculationService.Object, mockDateFilterService.Object, mockImportCalculator.Object, mockUsageDataRepository.Object);
            var fileMock = new Mock<IFormFile>();
            fileMock.Setup(f => f.Length).Returns(1024);
            fileMock.Setup(f => f.FileName).Returns("test.csv");
            string mapping = null;
            string provider = "TestProvider";
            int buildingId = 1;


            // Act
            var result = await controller.UploadCsv(fileMock.Object, mapping, provider, buildingId);

            // Assert
            Assert.IsType<BadRequestObjectResult>(result);
            Assert.Equal("Mapping informatie ontbreekt.", ((BadRequestObjectResult)result).Value);
        }

        [Fact]
        public async Task CheckIfBadRequestsAreTriggeredWhenFileIsNotACSV()
        {
            // Arrange
            var mockCalculationService = new Mock<IEnergyCalculationService>();
            var mockImportService = new Mock<IImportService>();
            var mockDateFilterService = new Mock<IDateFilterService>();
            var mockImportCalculator = new Mock<IImportCalculator>();
            var mockUsageDataRepository = new Mock<IUsageDataRepository>();
            var controller = new ImportController(mockImportService.Object, mockCalculationService.Object, mockDateFilterService.Object, mockImportCalculator.Object, mockUsageDataRepository.Object);
            var fileMock = new Mock<IFormFile>();
            fileMock.Setup(f => f.Length).Returns(1024);
            fileMock.Setup(f => f.FileName).Returns("test.txt");
            string mapping = "{\"Time\":\"Time\",\"ImportT1\":\"ImportT1\",\"ImportT2\":\"ImportT2\",\"ExportT1\":\"ExportT1\",\"ExportT2\":\"ExportT2\",\"L1MaxW\":\"L1MaxW\",\"L2MaxW\":\"L2MaxW\",\"L3MaxW\":\"L3MaxW\"}";
            string provider = "TestProvider";
            int buildingId = 1;

            // Act
            var result = await controller.UploadCsv(fileMock.Object, mapping, provider, buildingId);

            // Assert
            Assert.IsType<BadRequestObjectResult>(result);
            Assert.Equal("Alleen CSV-bestanden zijn toegestaan.", ((BadRequestObjectResult)result).Value);
        }

        [Fact]
        public async Task CheckIfBadRequestsAreTriggeredWhenFileSizeIsTooLarge()
        {
            // Arrange
            var mockCalculationService = new Mock<IEnergyCalculationService>();
            var mockImportService = new Mock<IImportService>();
            var mockDateFilterService = new Mock<IDateFilterService>();
            var mockImportCalculator = new Mock<IImportCalculator>();
            var mockUsageDataRepository = new Mock<IUsageDataRepository>();
            var controller = new ImportController(mockImportService.Object, mockCalculationService.Object, mockDateFilterService.Object, mockImportCalculator.Object, mockUsageDataRepository.Object);
            var fileMock = new Mock<IFormFile>();
            fileMock.Setup(f => f.Length).Returns(10 * 1024 * 1024 + 1);
            fileMock.Setup(f => f.FileName).Returns("test.csv");
            string mapping = "{\"Time\":\"Time\",\"ImportT1\":\"ImportT1\",\"ImportT2\":\"ImportT2\",\"ExportT1\":\"ExportT1\",\"ExportT2\":\"ExportT2\",\"L1MaxW\":\"L1MaxW\",\"L2MaxW\":\"L2MaxW\",\"L3MaxW\":\"L3MaxW\"}";
            string provider = "TestProvider";
            int buildingId = 1;

            // Act
            var result = await controller.UploadCsv(fileMock.Object, mapping, provider, buildingId);

            // Assert
            Assert.IsType<BadRequestObjectResult>(result);
            Assert.Equal("Bestand is te groot. Maximaal toegestaan is 10MB.", ((BadRequestObjectResult)result).Value);
        }

        [Fact]
        public async Task CheckIfBadRequestsAreNOTTriggeredWhenFileIsValid()
        {
            // Arrange
            var mockCalculationService = new Mock<IEnergyCalculationService>();
            var mockImportService = new Mock<IImportService>();
            var mockDateFilterService = new Mock<IDateFilterService>();
            var mockImportCalculator = new Mock<IImportCalculator>();
            var mockUsageDataRepository = new Mock<IUsageDataRepository>();
            var controller = new ImportController(mockImportService.Object, mockCalculationService.Object, mockDateFilterService.Object, mockImportCalculator.Object, mockUsageDataRepository.Object);
            var fileMock = new Mock<IFormFile>();
            fileMock.Setup(f => f.Length).Returns(1024);
            fileMock.Setup(f => f.FileName).Returns("test.csv");
            string mapping = "{\"Time\":\"Time\",\"ImportT1\":\"ImportT1\",\"ImportT2\":\"ImportT2\",\"ExportT1\":\"ExportT1\",\"ExportT2\":\"ExportT2\",\"L1MaxW\":\"L1MaxW\",\"L2MaxW\":\"L2MaxW\",\"L3MaxW\":\"L3MaxW\"}";
            string provider = "TestProvider";
            int buildingId = 1;

            // Act
            var result = await controller.UploadCsv(fileMock.Object, mapping, provider, buildingId);

            // Assert
            Assert.IsType<OkObjectResult>(result);
        }



        [Fact]
        public void CheckIfBadRequestAreTriggeredWhenInfoIsNotCompleteOrNotValid()
        {
            // Arrange
            var mockCalculationService = new Mock<IEnergyCalculationService>();
            var mockImportService = new Mock<IImportService>();
            var mockDateFilterService = new Mock<IDateFilterService>();
            var mockImportCalculator = new Mock<IImportCalculator>();
            var mockUsageDataRepository = new Mock<IUsageDataRepository>();
            var controller = new ImportController(mockImportService.Object, mockCalculationService.Object, mockDateFilterService.Object, mockImportCalculator.Object, mockUsageDataRepository.Object);
            var importData = new List<EnergyImportDTO>();

            // Act
            var result = controller.Calculate(importData, null);

            // Assert
            Assert.IsType<BadRequestObjectResult>(result);
            Assert.Equal("Geen of ongeldige data ontvangen.", ((BadRequestObjectResult)result).Value);
        }

        [Fact]
        public void CheckIfBadRequestAreTriggeredWhenDataContainsOneEnergyImportDTO()
        {
            // Arrange
            var mockCalculationService = new Mock<IEnergyCalculationService>();
            var mockImportService = new Mock<IImportService>();
            var mockDateFilterService = new Mock<IDateFilterService>();
            var mockImportCalculator = new Mock<IImportCalculator>();
            var mockUsageDataRepository = new Mock<IUsageDataRepository>();
            var controller = new ImportController(mockImportService.Object, mockCalculationService.Object, mockDateFilterService.Object, mockImportCalculator.Object, mockUsageDataRepository.Object);
            var importData = new List<EnergyImportDTO>
            {
                new EnergyImportDTO
                {
                    Time = DateTime.Now,
                    ImportT1 = 100,
                    ImportT2 = 150,
                    ExportT1 = 50,
                    ExportT2 = 75,
                    L1MaxW = 5000,
                    L2MaxW = 3000,
                    L3MaxW = 2000
                }
            };

            // Act
            var result = controller.Calculate(importData, null);

            // Assert
            Assert.IsType<BadRequestObjectResult>(result);
            Assert.Equal("Minimaal 2 datapunten zijn vereist voor berekening.", ((BadRequestObjectResult)result).Value);
        }

        [Fact]
        public void CheckIfBadRequestAreNOTTriggeredWhenDataIsValid()
        {
            // Arrange
            var mockCalculationService = new Mock<IEnergyCalculationService>();
            var mockImportService = new Mock<IImportService>();
            var mockDateFilterService = new Mock<IDateFilterService>();
            var mockImportCalculator = new Mock<IImportCalculator>();
            var mockUsageDataRepository = new Mock<IUsageDataRepository>();
            var controller = new ImportController(mockImportService.Object, mockCalculationService.Object, mockDateFilterService.Object, mockImportCalculator.Object, mockUsageDataRepository.Object);
            var providerName = "TestProvider";
            var importData = new List<EnergyImportDTO>
            {
                new EnergyImportDTO
                {
                    Time = DateTime.Now,
                    ImportT1 = 100,
                    ImportT2 = 150,
                    ExportT1 = 50,
                    ExportT2 = 75,
                    L1MaxW = 5000,
                    L2MaxW = 3000,
                    L3MaxW = 2000
                },
                new EnergyImportDTO
                {
                    Time = DateTime.Now.AddHours(1),
                    ImportT1 = 120,
                    ImportT2 = 160,
                    ExportT1 = 60,
                    ExportT2 = 80,
                    L1MaxW = 5500,
                    L2MaxW = 3500,
                    L3MaxW = 2500
                }
            };


            // Act
            var result = controller.Calculate(importData, providerName);

            // Assert
            Assert.IsType<OkObjectResult>(result);
        }

        [Fact]
        public async Task CheckIfBadRequestIsTriggeredWithInvalidData()
        {
            // Arrange
            var mockCalculationService = new Mock<IEnergyCalculationService>();
            var mockImportService = new Mock<IImportService>();
            var mockDateFilterService = new Mock<IDateFilterService>();
            var mockImportCalculator = new Mock<IImportCalculator>();
            var mockUsageDataRepository = new Mock<IUsageDataRepository>();
            var controller = new ImportController(mockImportService.Object, mockCalculationService.Object, mockDateFilterService.Object, mockImportCalculator.Object, mockUsageDataRepository.Object);
            var providerName = "TestProvider";
            var importData = new ImportRequestDTO
            {
                Data = new List<EnergyImportDTO>(),                
                CustomBattery = null
            };
           

            // Act
            var result = await controller.PostToDatabase(importData, providerName, 1);

            // Assert
            var badRequestResult = Assert.IsType<BadRequestObjectResult>(result);
            Assert.Equal("Geen of ongeldige data ontvangen.", badRequestResult.Value);
        }

        [Fact]
        public async Task CheckIfPostToDatabaseSucceedsWithRightInfo()
        {
            // Arrange
            var mockCalculationService = new Mock<IEnergyCalculationService>();
            var mockImportService = new Mock<IImportService>();
            var mockDateFilterService = new Mock<IDateFilterService>();
            var mockImportCalculator = new Mock<IImportCalculator>();
            var mockUsageDataRepository = new Mock<IUsageDataRepository>();
            var controller = new ImportController(mockImportService.Object, mockCalculationService.Object, mockDateFilterService.Object, mockImportCalculator.Object, mockUsageDataRepository.Object);
            var providerName = "TestProvider";
            var importData = new ImportRequestDTO
            {
                Data = new List<EnergyImportDTO>
                {
                    new EnergyImportDTO
                    {
                        Time = DateTime.Now,
                        ImportT1 = 100,
                        ImportT2 = 150,
                        ExportT1 = 50,
                        ExportT2 = 75,
                        L1MaxW = 5000,
                        L2MaxW = 3000,
                        L3MaxW = 2000
                    },
                    new EnergyImportDTO
                    {
                        Time = DateTime.Now.AddHours(1),
                        ImportT1 = 120,
                        ImportT2 = 160,
                        ExportT1 = 60,
                        ExportT2 = 80,
                        L1MaxW = 5500,
                        L2MaxW = 3500,
                        L3MaxW = 2500
                    }
                },
                CustomBattery = null
            };

            // Act
            var result = await controller.PostToDatabase(importData, providerName, 1);

            // Assert
            Assert.IsType<OkObjectResult>(result);
        }
    }

    
}
