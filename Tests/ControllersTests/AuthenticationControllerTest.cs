using _04._Tests.Builders;
using Energy_Truth.Shared.DTO_s;
using Energy_Truth.Shared.Login;
using Energy_Truth_WEB_API.Controllers;
using Energy_Truth_WEB_API.Services.Customer;
using Microsoft.AspNetCore.Mvc;
using Moq;

namespace _04._Tests.ControllersTests
{
    public class AuthenticationControllerTest
    {
        [Fact]
        public async Task CheckIfLoginSucceeds()
        {
            // Arrange
            var mockCustomerService = new Mock<ICustomerService>();
            var loginRequest = new LoginRequestBuilder().WithEmail("test@example.com").WithPassword("password").Build();
            var expectedUser = new LoggedInUserBuilder().WithEmail("test@example.com").WithIsLoggedIn(true).Build();

            mockCustomerService.Setup(s => s.LoginCustomerAsync(It.IsAny<LoginRequestDTO>()))
            .ReturnsAsync(expectedUser);

            //Act
            var authenticationController = new AuthenticationController(mockCustomerService.Object);
            var result = await authenticationController.Login(loginRequest);

            // Assert
            Assert.IsType<OkObjectResult>(result);
        }

        [Fact]
        public async Task CheckIfLoginFailsWithNonMatchingPasswords()
        {
            // Arrange
            var mockCustomerService = new Mock<ICustomerService>();
            var loginRequest = new LoginRequestBuilder().WithEmail("test@example.com").WithPassword("wrongpassword").Build();
            var expectedUser = new LoggedInUserBuilder().WithEmail("test@example.com").WithIsLoggedIn(false).Build();

            mockCustomerService.Setup(s => s.LoginCustomerAsync(It.IsAny<LoginRequestDTO>()))
            .ReturnsAsync(expectedUser);

            //Act
            var authenticationController = new AuthenticationController(mockCustomerService.Object);
            var result = await authenticationController.Login(loginRequest);

            // Assert
            var badRequestResult = Assert.IsType<BadRequestObjectResult>(result);
            Assert.Equal("Ongeldige inloggegevens.", badRequestResult.Value);
        }

        [Fact]
        public async Task CheckIfLoginFailsWithNullRequest()
        {
            // Arrange
            var mockCustomerService = new Mock<ICustomerService>();
            //Act
            var authenticationController = new AuthenticationController(mockCustomerService.Object);
            var result = await authenticationController.Login(null);
            // Assert
            var badRequestResult = Assert.IsType<BadRequestObjectResult>(result);
            Assert.Equal("Ongeldige aanvraag.", badRequestResult.Value);
        }

        [Fact]
        public async Task CheckIfLoginFailsWithExceptionWhenServiceThrowsException()
        {
            // Arrange
            var mockCustomerService = new Mock<ICustomerService>();
            var loginRequest = new LoginRequestBuilder().Build();

            mockCustomerService.Setup(s => s.LoginCustomerAsync(It.IsAny<LoginRequestDTO>()))
                .ThrowsAsync(new Exception("Service error"));

            // Act
            var authenticationController = new AuthenticationController(mockCustomerService.Object);
            var result = await authenticationController.Login(loginRequest);

            // Assert
            var statusCodeResult = Assert.IsType<ObjectResult>(result);
            Assert.Equal(500, statusCodeResult.StatusCode);
            Assert.Equal("Er is een fout opgetreden bij het inloggen. Probeer het later opnieuw.", statusCodeResult.Value);
        }

        [Fact]
        public async Task CheckIfCreateCustomerReturnsBadRequestWhenDTOIsNull()
        {
            // Arrange
            var mockCustomerService = new Mock<ICustomerService>();
            var controller = new AuthenticationController(mockCustomerService.Object);
            // Act
            var result = await controller.CreateCustomer(null);
            // Assert
            var badRequestResult = Assert.IsType<BadRequestObjectResult>(result);
            Assert.Equal("Ongeldige klantgegevens.", badRequestResult.Value);
        }

        [Fact]
        public async Task CheckIfBadRequestIsThrownWhenEmailIsEmpty()
        {
            // Arrange
            var mockCustomerService = new Mock<ICustomerService>();
            var controller = new AuthenticationController(mockCustomerService.Object);
            var registerRequest = new CreateCustomerDTOBuilder().WithEmail("").Build();
            // Act
            var result = await controller.CreateCustomer(registerRequest);
            // Assert
            var badRequestResult = Assert.IsType<BadRequestObjectResult>(result);
            Assert.Equal("E-mailadres is verplicht.", badRequestResult.Value);
        }

        [Fact]
        public async Task CheckIfBadRequestIsThrownWhenPasswordIsEmpty()
        {
            // Arrange
            var mockCustomerService = new Mock<ICustomerService>();
            var controller = new AuthenticationController(mockCustomerService.Object);
            var registerRequest = new CreateCustomerDTOBuilder().WithPassword("").Build();
            // Act
            var result = await controller.CreateCustomer(registerRequest);
            // Assert
            var badRequestResult = Assert.IsType<BadRequestObjectResult>(result);
            Assert.Equal("Wachtwoord is verplicht.", badRequestResult.Value);
        }

        [Fact]
        public async Task CheckIfBadRequestIsThrownWhenAddressIsEmpty()
        {
            // Arrange
            var mockCustomerService = new Mock<ICustomerService>();
            var controller = new AuthenticationController(mockCustomerService.Object);
            var registerRequest = new CreateCustomerDTOBuilder().WithAddress("").Build();
            // Act
            var result = await controller.CreateCustomer(registerRequest);
            // Assert
            var badRequestResult = Assert.IsType<BadRequestObjectResult>(result);
            Assert.Equal("Adres is verplicht.", badRequestResult.Value);
        }

        [Fact]
        public async Task CheckIfCreateCustomerSucceedsWhenValidDTOIsProvided()
        {
            // Arrange
            var mockCustomerService = new Mock<ICustomerService>();
            var registerRequest = new CreateCustomerDTOBuilder().Build();
            mockCustomerService.Setup(s => s.CreateCustomerAsync(It.IsAny<CreateCustomerDTO>())).ReturnsAsync(1);
            var controller = new AuthenticationController(mockCustomerService.Object);
            // Act
            var result = await controller.CreateCustomer(registerRequest);
            // Assert
            Assert.IsType<OkResult>(result);
        }

        [Fact]
        public async Task CheckIfCreateCustomerReturnsInternalServerErrorWhenServiceThrowsException()
        {
            // Arrange
            var mockCustomerService = new Mock<ICustomerService>();
            var registerRequest = new CreateCustomerDTOBuilder().Build();
            mockCustomerService.Setup(s => s.CreateCustomerAsync(It.IsAny<CreateCustomerDTO>()))
                .ThrowsAsync(new Exception("Service error"));
            var controller = new AuthenticationController(mockCustomerService.Object);
            // Act
            var result = await controller.CreateCustomer(registerRequest);
            // Assert
            var statusCodeResult = Assert.IsType<ObjectResult>(result);
            Assert.Equal(500, statusCodeResult.StatusCode);
            Assert.Equal("Er is een fout opgetreden bij het aanmaken van de klant. Probeer het later opnieuw.", statusCodeResult.Value);
        }

        [Fact]
        public async Task CheckIfCreateCustomerReturnsBadRequestIfEmailAlreadyExists()
        {
            // Arrange
            var mockCustomerService = new Mock<ICustomerService>();
            var registerRequest = new CreateCustomerDTOBuilder().WithEmail("existing@example.com").Build();
            mockCustomerService.Setup(s => s.CreateCustomerAsync(It.IsAny<CreateCustomerDTO>())).ReturnsAsync(0);
            var controller = new AuthenticationController(mockCustomerService.Object);
            // Act
            var result = await controller.CreateCustomer(registerRequest);
            // Assert
            var badRequestResult = Assert.IsType<BadRequestObjectResult>(result);
            Assert.Equal("Klant met dit e-mailadres bestaat al.", badRequestResult.Value);
        }

        [Fact]
        public async Task CheckIfCreateCustomerThrowsExceptionWhenCustomerIdIsNull()
        {
            // Arrange
            var mockCustomerService = new Mock<ICustomerService>();
            var registerRequest = new CreateCustomerDTOBuilder().WithEmail("existing@example.com").Build();
            mockCustomerService.Setup(s => s.CreateCustomerAsync(It.IsAny<CreateCustomerDTO>())).ReturnsAsync(null);
            var controller = new AuthenticationController(mockCustomerService.Object);
            // Act
            var result = await controller.CreateCustomer(registerRequest);
            // Assert
            var statusCodeResult = Assert.IsType<ObjectResult>(result);
            Assert.Equal("Er is een fout opgetreden bij het aanmaken van de klant. Probeer het later opnieuw.", statusCodeResult.Value);
        }
    }
}