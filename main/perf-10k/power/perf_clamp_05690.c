/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05690(unsigned int count)
{
    const unsigned int limit = 126u;
    return count > limit ? limit : count;
}
