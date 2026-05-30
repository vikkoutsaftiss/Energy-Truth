using Energy_Truth.Shared.Login;

namespace Energy_Truth_Presentation.Services
{
    public interface IAuthenticateService
    {
        LoggedInUser CurrentUser { get; }
        bool LogIn(LoggedInUser user);

        bool LogOut();
    }
}
