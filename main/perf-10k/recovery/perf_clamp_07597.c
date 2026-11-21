/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_07597(unsigned int count)
{
    const unsigned int limit = 175u;
    return count > limit ? limit : count;
}
