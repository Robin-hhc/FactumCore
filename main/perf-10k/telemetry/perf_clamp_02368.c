/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02368(unsigned int count)
{
    const unsigned int limit = 175u;
    return count > limit ? limit : count;
}
