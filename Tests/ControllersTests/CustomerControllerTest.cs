using _04._Tests.Builders;
using Energy_Truth.Shared.DTO_s;
using Energy_Truth_WEB_API.Controllers;
using Energy_Truth_WEB_API.Services.Customer;
using Microsoft.AspNetCore.Mvc;
using Moq;

namespace _04._Tests.ControllersTests
{
    public class CustomerControllerTest
    {
        
        [Fact]
        public async Task CheckIfCreateCustomerSucceeds()
        {
            // Arrange
            var mockCustomerService = new Mock<ICustomerService>();
            mockCustomerService
                .Setup(s => s.CreateCustomerAsync(It.IsAny<CreateCustomerDTO>()))
                .ReturnsAsync(1);
            var controller = new CustomerController(mockCustomerService.Object);
            var customerDTO = new CreateCustomerDTOBuilder().Build();

            // Act
            var result = await controller.CreateCustomer(customerDTO);

            // Assert
            Assert.IsType<OkObjectResult>(result);
        }

        [Fact]
        public async Task CheckIfCreateCustomerReturnsBadRequestWhenDTOIsNull()
        {
            // Arrange
            var mockCustomerService = new Mock<ICustomerService>();
            var controller = new CustomerController(mockCustomerService.Object);

            // Act
            var result = await controller.CreateCustomer(null);

            // Assert
            Assert.IsType<BadRequestObjectResult>(result);
        }

        [Fact]
        public async Task CheckIfCreateCustomerReturnsBadRequestWhenEmailIsEmpty()
        {
            // Arrange
            var mockCustomerService = new Mock<ICustomerService>();
            var controller = new CustomerController(mockCustomerService.Object);
            var customerDTO = new CreateCustomerDTOBuilder().WithEmail("").Build();

            // Act
            var result = await controller.CreateCustomer(customerDTO);

            // Assert
            Assert.IsType<BadRequestObjectResult>(result);
        }

        [Fact]
        public async Task CheckIfCreateCustomerReturnsBadRequestWhenPasswordIsEmpty()
        {
            // Arrange
            var mockCustomerService = new Mock<ICustomerService>();
            var controller = new CustomerController(mockCustomerService.Object);
            var customerDTO = new CreateCustomerDTOBuilder().WithPassword("").Build();

            // Act
            var result = await controller.CreateCustomer(customerDTO);

            // Assert
            Assert.IsType<BadRequestObjectResult>(result);
        }

        [Fact]
        public async Task CheckIfCreateCustomerReturnsBadRequestWhenAddressIsEmpty()
        {
            var mockCustomerService = new Mock<ICustomerService>();
            mockCustomerService.Setup(s => s.CreateCustomerAsync(It.IsAny<CreateCustomerDTO>())).ReturnsAsync(1);
            var controller = new CustomerController(mockCustomerService.Object);
            var customerDTO = new CreateCustomerDTOBuilder().WithAddress("").Build();

            var result = await controller.CreateCustomer(customerDTO);

            Assert.IsType<BadRequestObjectResult>(result);
        }

        
        [Fact]
        public async Task CheckIfCreateCustomerReturnsBadRequestWhenCustomerAlreadyExists()
        {
            var mockCustomerService = new Mock<ICustomerService>();
            mockCustomerService.Setup(s => s.CreateCustomerAsync(It.IsAny<CreateCustomerDTO>())).ReturnsAsync(0);
            var controller = new CustomerController(mockCustomerService.Object);
            var customerDTO = new CreateCustomerDTOBuilder().Build();

            var result = await controller.CreateCustomer(customerDTO);

            Assert.IsType<BadRequestObjectResult>(result);
        }
    }
}