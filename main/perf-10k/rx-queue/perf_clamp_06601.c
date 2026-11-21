/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06601(unsigned int count)
{
    const unsigned int limit = 175u;
    return count > limit ? limit : count;
}
