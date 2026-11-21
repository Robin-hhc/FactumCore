/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06316(unsigned int count)
{
    const unsigned int limit = 61u;
    return count > limit ? limit : count;
}
