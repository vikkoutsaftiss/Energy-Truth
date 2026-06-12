using _04._Tests.Builders;
using Energy_Truth.Shared.DTO_s;
using Energy_Truth.Shared.Repositories;
using Energy_Truth_WEB_API.Services.Customer;
using Moq;
using System;
using System.Collections.Generic;
using System.Text;

namespace _04._Tests.ServicesTests
{
    public class CustomerServiceTest
    {
        [Fact]
        public async Task CheckIfCreateCustomerSucceedsWithStandardCustomer()
        {
            // Arrange
            var mockCustomerRepository = new Mock<ICustomerRepository>();
            var expectedCustomer = new CreateCustomerDTOBuilder().Build();
            mockCustomerRepository.Setup(r => r.GetCustomerByEmailAsync(It.IsAny<string>())).ReturnsAsync(0);
            mockCustomerRepository.Setup(r => r.CreateCustomerAsync(It.IsAny<CreateCustomerDTO>())).ReturnsAsync(1);
            var customerService = new CustomerService(mockCustomerRepository.Object);
            // Act
            var result = await customerService.CreateCustomerAsync(expectedCustomer);
            // Assert
            Assert.Equal(1, result);
        }

        [Fact]
        public async Task CheckIfCreateCustomerThrowsExceptionWhenCustomerAlreadyExists()
        {
            // Arrange
            var mockCustomerRepository = new Mock<ICustomerRepository>();
            var customerDTO = new CreateCustomerDTOBuilder().Build();
            mockCustomerRepository.Setup(r => r.GetCustomerByEmailAsync(It.IsAny<string>()))
                .ReturnsAsync(1);
            var customerService = new CustomerService(mockCustomerRepository.Object);
            // Act & Assert
            var exception = await Assert.ThrowsAsync<InvalidOperationException>(
                () => customerService.CreateCustomerAsync(customerDTO)
            );
            Assert.Equal("Dit e-mailadres is al geregistreerd.", exception.Message);
        }

        [Fact]
        public async Task CheckIfLoginCustomerReturnsCustomerObjectWhenSuccess()
        {
            // Arrange
            var mockCustomerRepository = new Mock<ICustomerRepository>();
            var loginRequest = new LoginRequestBuilder().WithPassword("hashedpassword").Build();
            var customerAuth = new CustomerAuthDTOBuilder().WithPasswordHash(BCrypt.Net.BCrypt.HashPassword("hashedpassword")).Build();
            mockCustomerRepository.Setup(r => r.GetCustomerAuthByEmailAsync(It.IsAny<string>()))
                .ReturnsAsync(customerAuth);
            var customerService = new CustomerService(mockCustomerRepository.Object);

            // Act
            var result = await customerService.LoginCustomerAsync(loginRequest);

            // Assert
            Assert.NotNull(result);
            Assert.Equal(customerAuth.Email, result.Email);
            Assert.True(result.IsLoggedIn);
            Assert.Equal(customerAuth.Id, result.Id);
        }

    }
}

