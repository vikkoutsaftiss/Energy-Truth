using Energy_Truth.E2ETests.PageObjects;
using Microsoft.Playwright;

namespace Energy_Truth.E2ETests
{
    [Parallelizable(ParallelScope.Self)]
    [TestFixture]
    public class AddBuildingTests : PageTest
    {
        public override BrowserNewContextOptions ContextOptions()
        {
            return new BrowserNewContextOptions()
            {
                ViewportSize = new ViewportSize { Width = 1280, Height = 1024 }
            };
        }

        [SetUp]
        public async Task Setup()
        {
            Page.Console += (_, msg) => Console.WriteLine($"BROWSER: {msg.Type}: {msg.Text}");
            Page.PageError += (_, err) => Console.WriteLine($"PAGE ERROR: {err}");

            var loginPage = new LoginPage(Page);
            await loginPage.GoToLoginAsync();
            await loginPage.LoginAsync("testhash", "123");
        }

        [Test]
        public async Task CanAddBuilding()
        {
            var postcode = $"{Random.Shared.Next(1000, 9999)}AA";

            var buildingPage = new BuildingAddPageObject(Page);
            await buildingPage.GoToBuildingPageAsync();
            await buildingPage.FillPostalCodeAsync(postcode);
            await buildingPage.FillConstructionYearAsync("2005");
            await buildingPage.SelectEnergyLabelAsync("C");
            await buildingPage.SubmitAsync();

            Assert.That(Page.Url, Does.Contain("/buildinglist"));
        }
    }
}