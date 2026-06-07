using Microsoft.Playwright;

namespace Energy_Truth.E2ETests.PageObjects
{
    public class LoginPage
    {
        private readonly IPage _page;

        public LoginPage(IPage page)
        {
            _page = page;
        }

        public async Task GoToLoginAsync()
        {
            await _page.GotoAsync("https://localhost:7140/login");
            await _page.WaitForSelectorAsync("[data-testid='username-field']", new()
            {
                State = WaitForSelectorState.Visible,
            });
        }

        public async Task LoginAsync(string username, string password)
        {
            await _page.Locator("[data-testid='username-field'] input").FillAsync(username);
            await _page.Locator("[data-testid='password-field'] input").FillAsync(password);
            await _page.ClickAsync("[data-testid='login-button']");

            await _page.WaitForURLAsync("**/building**");
        }
    }
}
