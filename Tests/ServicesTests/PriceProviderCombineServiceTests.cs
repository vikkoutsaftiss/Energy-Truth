using Energy_Truth_WEB_API.Services;
using Moq;
using Energy_Truth.Shared;
using Energy_Truth_WEB_API.Services.Provider;

namespace _04._Tests.ServicesTests
{
    public class PriceProviderCombineServiceTests
    {
        [Fact]
        public async Task CheckIfPriceIsJoinedToRightProvider()
        {
            //Arrange
            var mockProviderService = new Mock<IProviderService>();
            mockProviderService.Setup(service => service.GetProvidersAsync()).ReturnsAsync(new List<ProviderDTO>
            {
                new ProviderDTO { Code = "PA", Name = "Provider A" },
                new ProviderDTO { Code = "PB", Name = "Provider B" }
            });
            
            var mockPriceService = new Mock<IPriceService>();
            mockPriceService.Setup(service => service.GetCurrentPriceAsync()).ReturnsAsync(new List<PriceDTO>
            {
                new PriceDTO { ProviderCode = "PA", Price = 100 },
                new PriceDTO { ProviderCode = "PB", Price = 200 }
            });

            var combineService = new PriceProviderCombineService(mockProviderService.Object, mockPriceService.Object);

            //Act

            var result = await combineService.Combine();
            var providerA = result.First(x => x.ProviderCode == "PA");
            var providerB = result.First(x => x.ProviderCode == "PB");

            //Assert
            Assert.Equal("Provider A", providerA.ProviderName);
            Assert.Equal(100, providerA.Price);
            Assert.Equal("Provider B", providerB.ProviderName);
            Assert.Equal(200, providerB.Price); 
        }
    }
}
