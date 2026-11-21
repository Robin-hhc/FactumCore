/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_00886(unsigned int count)
{
    const unsigned int limit = 130u;
    return count > limit ? limit : count;
}
