using Energy_Truth.E2ETests.PageObjects;
using Microsoft.Playwright;

namespace Energy_Truth.E2ETests
{
    [Parallelizable(ParallelScope.Self)]
    [TestFixture]
    public class ImporterTests : PageTest
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
            await loginPage.LoginAsync("admin", "password");
        }
        

        [Test]
        public async Task CanUploadCSVWithHomeWizardAsChosenProvider()
        {            
            var csvImporterPage = new CsvImporterPage(Page);
            
            await csvImporterPage.SelectProviderAsync("Home Wizard");
            await csvImporterPage.UploadFileAsync(Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "TestData", "test-HomeWizard.csv"));
            await csvImporterPage.ProcessDataAsync();
            await csvImporterPage.StartCalculationAsync();

            await csvImporterPage.IsCalculationResultVisibleAsync();
        }

        [Test]
        public async Task CanUploadCSVWithUMeterAsChosenProvider()
        {
            var csvImporterPage = new CsvImporterPage(Page);

            await csvImporterPage.SelectProviderAsync("UMeter");
            await csvImporterPage.UploadFileAsync(Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "TestData", "test-UMeter.csv"));
            await csvImporterPage.ProcessDataAsync();
            await csvImporterPage.StartCalculationAsync();

            await csvImporterPage.IsCalculationResultVisibleAsync();
        }
    }
}
