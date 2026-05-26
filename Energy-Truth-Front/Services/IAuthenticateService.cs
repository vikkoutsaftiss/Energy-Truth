using Energy_Truth.Shared.Login;

namespace Energy_Truth_Presentation.Services
{
    public interface IAuthenticateService
    {
        User CurrentUser { get; }
        bool LogIn(User user);

        bool LogOut();
    }
}
