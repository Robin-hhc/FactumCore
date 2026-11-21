/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05318(unsigned int count)
{
    const unsigned int limit = 27u;
    return count > limit ? limit : count;
}
